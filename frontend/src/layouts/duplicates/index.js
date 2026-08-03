
import { useCallback, useEffect, useRef, useState } from "react";
import PropTypes from "prop-types";

import Card from "@mui/material/Card";
import CircularProgress from "@mui/material/CircularProgress";
import Grid from "@mui/material/Grid";
import Tooltip from "@mui/material/Tooltip";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDAlert from "components/MDAlert";
import MDButton from "components/MDButton";

import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";

import { CefrBadge, SimilarityBar } from "components/EflShared";
import { usePipeline } from "context/PipelineContext";
import {
  getDuplicates,
  getResourceDetail,
  resolveDuplicate,
  rescanDuplicates,
} from "services/endpoints";
import colors from "assets/theme/base/colors";

const CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];

const MERGE_TOOLTIP =
  "Full content merge is out of scope for this feasibility study. " +
  "Server-side, “merged” is recorded like “kept_both”: both resources stay; " +
  "the pair is only marked resolved.";

function pairKey(a, b) {
  return [String(a || ""), String(b || "")].sort().join("|");
}

function feedKey(item) {
  return `${item.type}|${item.timestamp}|${item.resource_id_a}|${item.resource_id_b}|${item.similarity}`;
}

function cefrOk(level) {
  return level && CEFR_LEVELS.includes(level);
}

function MiniResourceCard({ resource }) {
  const r = resource || {};
  const title = r.title || r.resource_id || "Unknown resource";
  const snippet = r.snippet || r.raw_text_preview || "";

  return (
    <Card
      variant="outlined"
      sx={{
        height: "100%",
        borderColor: colors.grey[300],
        boxShadow: "none",
      }}
    >
      <MDBox p={1.5}>
        <MDBox display="flex" alignItems="center" gap={1} mb={0.75} flexWrap="wrap">
          <MDTypography variant="button" fontWeight="bold" sx={{ flex: 1, minWidth: 0 }}>
            {title}
          </MDTypography>
          {cefrOk(r.cefr_level) && <CefrBadge level={r.cefr_level} />}
        </MDBox>
        <MDTypography variant="caption" color="text" display="block" mb={0.5}>
          {r.resource_id}
        </MDTypography>
        <MDTypography
          variant="caption"
          sx={{
            color: colors.text.focus,
            display: "-webkit-box",
            WebkitLineClamp: 3,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {snippet || "No snippet available."}
        </MDTypography>
      </MDBox>
    </Card>
  );
}

MiniResourceCard.propTypes = {
  resource: PropTypes.shape({
    resource_id: PropTypes.string,
    title: PropTypes.string,
    cefr_level: PropTypes.string,
    snippet: PropTypes.string,
    raw_text_preview: PropTypes.string,
  }),
};

function sideFromDetail(id, detail, fallbackTitle) {
  if (!id) {
    return { resource_id: "", title: fallbackTitle || "—", snippet: "" };
  }
  if (id === "pending") {
    return {
      resource_id: "pending",
      title: fallbackTitle || "Pending upload (not indexed)",
      cefr_level: null,
      snippet: "Detected during Resource Analyzer before indexing.",
    };
  }
  if (!detail) {
    return {
      resource_id: id,
      title: fallbackTitle || id,
      snippet: "",
    };
  }
  const raw = detail.raw_text_preview || detail.raw_text || "";
  const snippet = raw.length > 160 ? `${String(raw).slice(0, 160)}…` : String(raw || "");
  return {
    resource_id: detail.resource_id || id,
    title: detail.title || id,
    cefr_level: detail.cefr_level,
    skill_type: detail.skill_type,
    topic_domain: detail.topic_domain,
    snippet,
  };
}

async function enrichLiveFlag(item) {
  const a = item.resource_id_a;
  const b = item.resource_id_b;
  const [detailA, detailB] = await Promise.all([
    a && a !== "pending" ? getResourceDetail(a).catch(() => null) : Promise.resolve(null),
    b && b !== "pending" ? getResourceDetail(b).catch(() => null) : Promise.resolve(null),
  ]);
  return {
    resource_id_a: a,
    resource_id_b: b,
    similarity: Number(item.similarity) || 0,
    resource_a: sideFromDetail(a, detailA),
    resource_b: sideFromDetail(b, detailB),
    _live: true,
  };
}

function DuplicatePairRow({ pair, busy, onResolve }) {
  const a = pair.resource_a || { resource_id: pair.resource_id_a };
  const b = pair.resource_b || { resource_id: pair.resource_id_b };
  const pendingSide = pair.resource_id_a === "pending" || pair.resource_id_b === "pending";

  return (
    <Card sx={{ mb: 2 }}>
      <MDBox p={2}>
        <Grid container spacing={2} alignItems="stretch">
          <Grid item xs={12} md={4}>
            <MiniResourceCard resource={a} />
          </Grid>
          <Grid item xs={12} md={4}>
            <MDBox
              display="flex"
              flexDirection="column"
              alignItems="center"
              justifyContent="center"
              height="100%"
              gap={1}
              px={1}
            >
              <MDTypography variant="caption" fontWeight="medium" color="text">
                Similarity
              </MDTypography>
              <MDBox width="100%" maxWidth="14rem">
                <SimilarityBar value={Number(pair.similarity) || 0} />
              </MDBox>
              {pair._live && (
                <MDTypography variant="caption" color="info">
                  Live flag
                </MDTypography>
              )}
            </MDBox>
          </Grid>
          <Grid item xs={12} md={4}>
            <MiniResourceCard resource={b} />
          </Grid>
        </Grid>

        <MDBox display="flex" flexWrap="wrap" gap={1} mt={2} justifyContent="flex-end">
          <MDButton
            variant="outlined"
            color="secondary"
            size="small"
            disabled={busy}
            onClick={() => onResolve(pair, "kept_both")}
          >
            Keep Both
          </MDButton>
          <Tooltip title={MERGE_TOOLTIP} arrow>
            <span>
              <MDButton
                variant="outlined"
                color="info"
                size="small"
                disabled={busy}
                onClick={() => onResolve(pair, "merged")}
              >
                Merge
              </MDButton>
            </span>
          </Tooltip>
          <MDButton
            variant="gradient"
            color="error"
            size="small"
            disabled={busy || pendingSide}
            onClick={() => onResolve(pair, "deleted_b")}
          >
            Delete Second
          </MDButton>
        </MDBox>
        {pendingSide && (
          <MDTypography variant="caption" color="text" mt={1} display="block">
            Delete Second is disabled while one side is a pending (not-yet-indexed) upload.
          </MDTypography>
        )}
      </MDBox>
    </Card>
  );
}

DuplicatePairRow.propTypes = {
  pair: PropTypes.object.isRequired,
  busy: PropTypes.bool,
  onResolve: PropTypes.func.isRequired,
};

function Duplicates() {
  const { liveActivityFeed } = usePipeline();

  const [pairs, setPairs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [rescanning, setRescanning] = useState(false);
  const [resolvingKey, setResolvingKey] = useState(null);

  const seenFlags = useRef(new Set());
  const primed = useRef(false);
  const pairsRef = useRef(pairs);
  pairsRef.current = pairs;
  const feedRef = useRef(liveActivityFeed);
  feedRef.current = liveActivityFeed;

  const loadList = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDuplicates();
      setPairs(Array.isArray(data?.duplicates) ? data.duplicates : []);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Failed to load duplicates";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    (async () => {
      await loadList();
      const seed = new Set();
      (feedRef.current || [])
        .filter((item) => item?.type === "duplicate_flag")
        .forEach((item) => seed.add(feedKey(item)));
      seenFlags.current = seed;
      primed.current = true;
    })();
  }, [loadList]);

  useEffect(() => {
    if (!primed.current) return;

    const fresh = (liveActivityFeed || []).filter(
      (item) =>
        item?.type === "duplicate_flag" &&
        item.resource_id_a &&
        item.resource_id_b &&
        !seenFlags.current.has(feedKey(item))
    );
    if (!fresh.length) return;

    fresh.forEach((item) => seenFlags.current.add(feedKey(item)));

    (async () => {
      for (const item of fresh) {
        const key = pairKey(item.resource_id_a, item.resource_id_b);
        if (pairsRef.current.some((p) => pairKey(p.resource_id_a, p.resource_id_b) === key)) {
          continue;
        }
        try {
          const enriched = await enrichLiveFlag(item);
          setPairs((prev) => {
            if (
              prev.some(
                (p) =>
                  pairKey(p.resource_id_a, p.resource_id_b) ===
                  pairKey(enriched.resource_id_a, enriched.resource_id_b)
              )
            ) {
              return prev;
            }
            return [enriched, ...prev];
          });
        } catch {

        }
      }
    })();
  }, [liveActivityFeed]);

  const handleResolve = async (pair, action) => {
    const key = pairKey(pair.resource_id_a, pair.resource_id_b);
    setActionError(null);
    setResolvingKey(key);
    try {
      await resolveDuplicate({
        resource_id_a: pair.resource_id_a,
        resource_id_b: pair.resource_id_b,
        action,
      });
      setPairs((prev) => prev.filter((p) => pairKey(p.resource_id_a, p.resource_id_b) !== key));
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Resolve failed";
      setActionError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setResolvingKey(null);
    }
  };

  const handleRescan = async () => {
    setRescanning(true);
    setActionError(null);
    try {
      const data = await rescanDuplicates();
      setPairs(Array.isArray(data?.duplicates) ? data.duplicates : []);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Rescan failed";
      setActionError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setRescanning(false);
    }
  };

  return (
    <DashboardLayout>
      <DashboardNavbar />
      <MDBox py={3}>
        <MDBox
          display="flex"
          flexWrap="wrap"
          alignItems="flex-start"
          justifyContent="space-between"
          gap={2}
          mb={2}
        >
          <MDBox>
            <MDTypography variant="h4" fontWeight="bold" mb={0.5}>
              Duplicate Detection
            </MDTypography>
            <MDTypography variant="button" color="text">
              Near-duplicate pairs from the index (≥ 0.97 similarity)
            </MDTypography>
          </MDBox>
          <MDButton variant="gradient" color="primary" onClick={handleRescan} disabled={rescanning}>
            {rescanning ? (
              <MDBox display="inline-flex" alignItems="center" gap={1}>
                <CircularProgress size={16} color="inherit" />
                Rescanning…
              </MDBox>
            ) : (
              "Rescan Index"
            )}
          </MDButton>
        </MDBox>

        {error && (
          <MDBox mb={2}>
            <MDAlert color="error">{error}</MDAlert>
          </MDBox>
        )}
        {actionError && (
          <MDBox mb={2}>
            <MDAlert color="error">{actionError}</MDAlert>
          </MDBox>
        )}

        {loading && (
          <MDTypography variant="button" color="text" mb={2} display="block">
            Loading candidates…
          </MDTypography>
        )}

        {!loading && !error && pairs.length === 0 && (
          <Card>
            <MDBox p={3} textAlign="center">
              <MDTypography variant="h6" fontWeight="medium" mb={0.5}>
                No duplicate candidates found
              </MDTypography>
              <MDTypography variant="button" color="text">
                Run Rescan Index after Train, or upload near-duplicates via the Analyzer to populate
                this list.
              </MDTypography>
            </MDBox>
          </Card>
        )}

        {pairs.map((pair) => {
          const key = pairKey(pair.resource_id_a, pair.resource_id_b);
          return (
            <DuplicatePairRow
              key={key}
              pair={pair}
              busy={resolvingKey === key || rescanning}
              onResolve={handleResolve}
            />
          );
        })}
      </MDBox>
      <Footer />
    </DashboardLayout>
  );
}

export default Duplicates;
