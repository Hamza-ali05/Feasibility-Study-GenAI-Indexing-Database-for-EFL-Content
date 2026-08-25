import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import PropTypes from "prop-types";

import { PIPELINE_STAGE_NAMES } from "components/EflShared/PipelineProgressBar";
import { getPipelineStatus } from "services/endpoints";
import { connectPipelineSocket, disconnectSocket } from "services/socket";
import { humanizeSearchQuery } from "utils/humanizeSearchQuery";

const MAX_FEED = 40;

function formatSearchActivityMessage(query, resultCount) {
  const label = humanizeSearchQuery(query);
  const hits = resultCount ?? 0;
  return `Search “${label}” (${hits} hits)`;
}

function emptyStages() {
  return PIPELINE_STAGE_NAMES.map((name) => ({
    name,
    status: "PENDING",
    progress_pct: null,
    run_at: null,
    error: null,
  }));
}

function activityId(item) {
  return `${item.type || "event"}|${item.timestamp || ""}|${item.stage || ""}|${item.query || ""}|${
    item.resource_id_a || ""
  }`;
}

function feedItemFromWs(msg) {
  const ts = msg.timestamp || new Date().toISOString();
  if (msg.type === "pipeline_update") {
    return {
      type: "pipeline",
      stage: msg.stage,
      status: msg.status,
      timestamp: ts,
      message: `${msg.stage} → ${msg.status}`,
    };
  }
  if (msg.type === "search_event") {
    return {
      type: "search_event",
      query: msg.query,
      result_count: msg.result_count,
      timestamp: ts,
      message: formatSearchActivityMessage(msg.query, msg.result_count),
    };
  }
  if (msg.type === "duplicate_flag") {
    return {
      type: "duplicate_flag",
      resource_id_a: msg.resource_id_a,
      resource_id_b: msg.resource_id_b,
      similarity: msg.similarity,
      timestamp: ts,
      message: `Duplicate flagged (${Number(msg.similarity || 0).toFixed(2)} similarity)`,
    };
  }
  return null;
}

function feedItemFromSummary(row) {
  const ts = row.timestamp;
  if (!ts) return null;
  if (row.type === "pipeline") {
    return {
      type: "pipeline",
      stage: row.stage,
      status: row.status,
      timestamp: ts,
      message: `${row.stage} → ${row.status}`,
    };
  }
  if (row.type === "predict") {
    return {
      type: "predict",
      timestamp: ts,
      message: `Predict run (${row.result_count ?? 0} results)`,
    };
  }
  if (row.type === "search" || row.type === "search_event") {
    return {
      type: "search_event",
      query: row.query,
      result_count: row.result_count,
      timestamp: ts,
      message: formatSearchActivityMessage(row.query, row.result_count),
    };
  }
  if (row.type === "duplicate" || row.type === "duplicate_flag") {
    return {
      type: "duplicate_flag",
      resource_id_a: row.resource_id_a,
      resource_id_b: row.resource_id_b,
      similarity: row.similarity,
      timestamp: ts,
      message: row.message || "Duplicate flagged",
    };
  }
  return {
    type: row.type || "event",
    timestamp: ts,
    message: row.message || row.type || "Activity",
  };
}

function normalizeFeedItem(item) {
  if (!item || !item.timestamp) return null;
  if (item.type === "search_event" || item.type === "search") {
    return {
      ...item,
      type: "search_event",
      message: formatSearchActivityMessage(item.query, item.result_count),
    };
  }
  return item;
}

function mergeFeed(prev, incoming) {
  const map = new Map();
  // Older first, then newer — so fresh humanized rows replace stale raw messages.
  [...prev, ...incoming].forEach((raw) => {
    const item = normalizeFeedItem(raw);
    if (!item) return;
    map.set(activityId(item), item);
  });
  return Array.from(map.values())
    .sort((a, b) => String(b.timestamp).localeCompare(String(a.timestamp)))
    .slice(0, MAX_FEED);
}

const PipelineContext = createContext(null);

function PipelineProvider({ children }) {
  const [connected, setConnected] = useState(false);
  const [stages, setStages] = useState(emptyStages);
  const [pipelineReady, setPipelineReady] = useState(false);
  const [liveActivityFeed, setLiveActivityFeed] = useState([]);
  const [analyzerStepsSeen, setAnalyzerStepsSeen] = useState([]);
  const [analyzerLatest, setAnalyzerLatest] = useState(null);
  const socketRef = useRef(null);

  const stagesComplete = useMemo(
    () => stages.filter((s) => s.status === "COMPLETE").length,
    [stages]
  );

  const applyStageUpdate = useCallback((stageName, status, extra = {}) => {
    if (!stageName || !PIPELINE_STAGE_NAMES.includes(stageName)) return;
    setStages((prev) =>
      prev.map((s) =>
        s.name === stageName
          ? {
              ...s,
              status: status || s.status,
              progress_pct: extra.progress_pct !== undefined ? extra.progress_pct : s.progress_pct,
              run_at: extra.run_at !== undefined ? extra.run_at : s.run_at,
              error: extra.error !== undefined ? extra.error : s.error,
            }
          : s
      )
    );
  }, []);

  const hydrateFromStatus = useCallback(async () => {
    try {
      const data = await getPipelineStatus();
      if (data && Array.isArray(data.stages)) {
        setStages(
          PIPELINE_STAGE_NAMES.map((name) => {
            const found = data.stages.find((s) => s.name === name);
            return {
              name,
              status: found?.status || "PENDING",
              progress_pct: found?.progress_pct ?? null,
              run_at: found?.run_at ?? null,
              error: found?.error ?? null,
            };
          })
        );
      }
      if (typeof data?.pipeline_ready === "boolean") {
        setPipelineReady(data.pipeline_ready);
      }
    } catch (err) {}
  }, []);

  const mergeSummaryActivity = useCallback((recentActivity) => {
    if (!Array.isArray(recentActivity)) return;
    const mapped = recentActivity.map(feedItemFromSummary).filter(Boolean);
    setLiveActivityFeed((prev) => mergeFeed(prev, mapped));
  }, []);

  const resetAnalyzerProgress = useCallback(() => {
    setAnalyzerStepsSeen([]);
    setAnalyzerLatest(null);
  }, []);

  const handleMessage = useCallback(
    (msg) => {
      if (!msg || typeof msg !== "object") return;

      if (msg.type === "pipeline_update") {
        applyStageUpdate(msg.stage, msg.status, {
          progress_pct: msg.progress_pct,
          error: msg.error,
          run_at: msg.timestamp,
        });
        if (typeof msg.pipeline_ready === "boolean") {
          setPipelineReady(msg.pipeline_ready);
        }

        if (msg.stage === "Resource Analyzer") {
          const step = msg.step;
          if (typeof step === "string" && step) {
            setAnalyzerStepsSeen((prev) => {
              if (prev.includes(step)) return prev;
              return [...prev, step];
            });
          }
          setAnalyzerLatest(msg);
        }
        const item = feedItemFromWs(msg);
        if (item) {
          setLiveActivityFeed((prev) => mergeFeed(prev, [item]));
        }
        return;
      }

      if (msg.type === "search_event" || msg.type === "duplicate_flag") {
        const item = feedItemFromWs(msg);
        if (item) {
          setLiveActivityFeed((prev) => mergeFeed(prev, [item]));
        }
      }
    },
    [applyStageUpdate]
  );

  useEffect(() => {
    hydrateFromStatus();
    socketRef.current = connectPipelineSocket(handleMessage, setConnected);
    return () => {
      disconnectSocket(socketRef.current);
      socketRef.current = null;
    };
  }, [handleMessage, hydrateFromStatus]);

  const value = useMemo(
    () => ({
      connected,
      stages,
      stagesComplete,
      pipelineReady,
      setPipelineReady,
      liveActivityFeed,
      mergeSummaryActivity,
      hydrateFromStatus,
      analyzerStepsSeen,
      analyzerLatest,
      resetAnalyzerProgress,
    }),
    [
      connected,
      stages,
      stagesComplete,
      pipelineReady,
      liveActivityFeed,
      mergeSummaryActivity,
      hydrateFromStatus,
      analyzerStepsSeen,
      analyzerLatest,
      resetAnalyzerProgress,
    ]
  );

  return <PipelineContext.Provider value={value}>{children}</PipelineContext.Provider>;
}

PipelineProvider.propTypes = {
  children: PropTypes.node.isRequired,
};

function usePipeline() {
  const ctx = useContext(PipelineContext);
  if (!ctx) {
    throw new Error("usePipeline() must be used within a PipelineProvider");
  }
  return ctx;
}

export { PipelineProvider, usePipeline };
export default PipelineContext;
