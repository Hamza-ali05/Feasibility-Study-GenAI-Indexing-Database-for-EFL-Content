import { useCallback, useEffect, useRef, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import PropTypes from "prop-types";

import Card from "@mui/material/Card";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDInput from "components/MDInput";
import MDButton from "components/MDButton";
import MDAlert from "components/MDAlert";

import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";

import { CefrBadge } from "components/EflShared";
import DocumentPreviewModal from "components/EflShared/DocumentPreviewModal";

import { usePipeline } from "context/PipelineContext";
import { getAskStreamUrl } from "services/endpoints";
import colors from "assets/theme/base/colors";

function isAnthropicConfigError(detail) {
  const text = String(detail || "");
  return /ANTHROPIC_API_KEY/i.test(text) || /anthropic api authentication/i.test(text);
}

function dash(value) {
  const text = String(value || "").trim();
  return text || "—";
}

function cleanSourceTitle(title) {
  let text = String(title || "");
  text = text.replace(/https?:\/\/\S+/gi, " ");
  text = text.replace(/www\.\S+/gi, " ");
  text = text.replace(/\bgutenberg\b/gi, " ");
  text = text.replace(/["“”]/g, " ");
  text = text.replace(/\s+/g, " ").trim();
  if (text.length > 90) {
    text = `${text.slice(0, 87)}…`;
  }
  return text || "Untitled resource";
}

function AssistantSources({ sources, onOpenSource }) {
  if (!sources || sources.length === 0) return null;

  const columns = ["#", "Title", "CEFR", "Skill", "Topic"];
  const template = "48px minmax(140px, 1.6fr) 64px 100px 110px";

  return (
    <MDBox mt={1.5}>
      <MDTypography variant="caption" fontWeight="bold" color="text" display="block" mb={0.75}>
        Sources ({sources.length})
      </MDTypography>
      <MDBox sx={{ width: "100%", overflowX: "auto" }}>
        <MDBox role="table" sx={{ width: "100%", minWidth: 420 }}>
          <MDBox
            role="row"
            sx={{
              display: "grid",
              gridTemplateColumns: template,
              alignItems: "end",
              borderBottom: `1px solid ${colors.grey[300]}`,
            }}
          >
            {columns.map((c) => (
              <MDBox
                key={c}
                role="columnheader"
                px={1}
                py={0.75}
                sx={{
                  fontSize: "0.7rem",
                  fontWeight: 700,
                  color: colors.text.focus,
                  whiteSpace: "nowrap",
                }}
              >
                {c}
              </MDBox>
            ))}
          </MDBox>
          {sources.map((src, index) => {
            const cefrOk =
              src.cefr_level && ["A1", "A2", "B1", "B2", "C1", "C2"].includes(src.cefr_level);
            const cells = [
              String(index + 1),
              dash(cleanSourceTitle(src.title)),
              cefrOk ? src.cefr_level : "—",
              dash(src.skill_type),
              dash(src.topic_domain),
            ];
            return (
              <MDBox
                key={src.resource_id || index}
                role="row"
                onClick={() => src.resource_id && onOpenSource(src.resource_id)}
                sx={{
                  display: "grid",
                  gridTemplateColumns: template,
                  alignItems: "start",
                  borderBottom: `1px solid ${colors.grey[200]}`,
                  cursor: src.resource_id ? "pointer" : "default",
                  "&:hover": src.resource_id ? { backgroundColor: colors.grey[100] } : undefined,
                }}
              >
                {cells.map((cell, j) => (
                  <MDBox
                    key={`${src.resource_id || index}-${j}`}
                    role="cell"
                    px={1}
                    py={0.85}
                    sx={{
                      fontSize: "0.78rem",
                      fontWeight: j === 1 ? 600 : 400,
                      color: j === 1 ? colors.primary.main : colors.dark.main,
                      wordBreak: "break-word",
                      overflowWrap: "anywhere",
                    }}
                  >
                    {j === 2 && cefrOk ? <CefrBadge level={src.cefr_level} /> : cell}
                  </MDBox>
                ))}
              </MDBox>
            );
          })}
        </MDBox>
      </MDBox>
      <MDTypography variant="caption" color="text" display="block" mt={0.75}>
        Click a row to preview the full resource.
      </MDTypography>
    </MDBox>
  );
}

AssistantSources.propTypes = {
  sources: PropTypes.arrayOf(
    PropTypes.shape({
      resource_id: PropTypes.string,
      title: PropTypes.string,
      cefr_level: PropTypes.string,
      skill_type: PropTypes.string,
      topic_domain: PropTypes.string,
    })
  ),
  onOpenSource: PropTypes.func.isRequired,
};

AssistantSources.defaultProps = {
  sources: [],
};

const WELCOME_EXAMPLES = [
  "What A2 reading texts do we have about travel?",
  "Suggest a short Business English activity for B1 learners.",
  "How can I teach vocabulary about health using our library?",
  "Summarise a beginner-friendly culture story I could use in class.",
];

function WelcomeGuide({ onPickExample, disabled }) {
  return (
    <MDBox display="flex" justifyContent="flex-start" mb={1.5}>
      <MDBox
        maxWidth={{ xs: "96%", md: "85%" }}
        px={2}
        py={1.75}
        borderRadius="lg"
        sx={{
          backgroundColor: colors.white.main,
          border: `1px solid ${colors.grey[300]}`,
          backgroundImage: `linear-gradient(165deg, ${colors.grey[100]} 0%, #fff 60%)`,
        }}
      >
        <MDTypography variant="button" fontWeight="bold" display="block" mb={0.75}>
          Hi — I can help you explore your EFL library
        </MDTypography>
        <MDTypography variant="body2" color="text" sx={{ lineHeight: 1.6 }} mb={1.25}>
          Ask me in plain English about lessons, texts, and teaching ideas already indexed here. I
          pull answers from your resources and can point you to the sources I used.
        </MDTypography>
        <MDTypography variant="caption" fontWeight="medium" color="text" display="block" mb={1}>
          Try something like:
        </MDTypography>
        <MDBox display="flex" flexDirection="column" gap={0.75}>
          {WELCOME_EXAMPLES.map((example) => (
            <MDBox
              key={example}
              component="button"
              type="button"
              disabled={disabled}
              onClick={() => onPickExample(example)}
              sx={{
                textAlign: "left",
                cursor: disabled ? "not-allowed" : "pointer",
                border: `1px solid ${colors.grey[300]}`,
                borderRadius: "0.6rem",
                backgroundColor: "#fff",
                px: 1.25,
                py: 0.9,
                opacity: disabled ? 0.55 : 1,
                transition: "border-color 0.15s ease, background-color 0.15s ease",
                "&:hover": disabled
                  ? undefined
                  : {
                      borderColor: colors.info.main,
                      backgroundColor: colors.grey[100],
                    },
              }}
            >
              <MDTypography variant="caption" color="text" sx={{ lineHeight: 1.45 }}>
                “{example}”
              </MDTypography>
            </MDBox>
          ))}
        </MDBox>
        <MDTypography variant="caption" color="text" display="block" mt={1.5}>
          Tip: mention a CEFR level, skill (reading, speaking…), or topic when you can — it helps me
          find a better match.
        </MDTypography>
      </MDBox>
    </MDBox>
  );
}

WelcomeGuide.propTypes = {
  onPickExample: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};

WelcomeGuide.defaultProps = {
  disabled: false,
};

function AskAI() {
  const { stages, pipelineReady, hydrateFromStatus } = usePipeline();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [pipelineAlert, setPipelineAlert] = useState(false);
  const [configAlert, setConfigAlert] = useState(false);
  const [error, setError] = useState(null);
  const [previewId, setPreviewId] = useState(null);

  const listRef = useRef(null);
  const esRef = useRef(null);
  const assistantIdRef = useRef(null);

  const predictComplete =
    pipelineReady || stages.some((s) => s.name === "Predict" && s.status === "COMPLETE");

  useEffect(() => {
    hydrateFromStatus();
    return () => {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, [hydrateFromStatus]);

  useEffect(() => {
    setPipelineAlert(!predictComplete);
  }, [predictComplete]);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, streaming]);

  const patchAssistant = useCallback((id, patch) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch(m) } : m)));
  }, []);

  const handleSend = useCallback(() => {
    const question = input.trim();
    if (!question || streaming || !predictComplete) return;

    setConfigAlert(false);
    setError(null);
    setInput("");

    const userMsg = {
      id: `u-${Date.now()}`,
      role: "user",
      text: question,
    };
    const assistantId = `a-${Date.now()}`;
    assistantIdRef.current = assistantId;
    const assistantMsg = {
      id: assistantId,
      role: "assistant",
      text: "",
      sources: null,
      streaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setStreaming(true);

    if (esRef.current) {
      esRef.current.close();
    }

    const url = getAskStreamUrl(question, 5);
    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = (event) => {
      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch (err) {
        return;
      }

      const id = assistantIdRef.current;
      if (!id) return;

      if (payload.type === "done" && Array.isArray(payload.sources)) {
        patchAssistant(id, () => ({ sources: payload.sources }));
        return;
      }

      if (payload.type === "token" && typeof payload.text === "string") {
        patchAssistant(id, (m) => ({ text: (m.text || "") + payload.text }));
        return;
      }

      if (payload.type === "complete") {
        patchAssistant(id, () => ({ streaming: false }));
        setStreaming(false);
        es.close();
        esRef.current = null;
        return;
      }

      if (payload.type === "error") {
        const detail = payload.detail || "Stream error";
        if (isAnthropicConfigError(detail)) {
          setConfigAlert(true);
          patchAssistant(id, () => ({
            text: "",
            streaming: false,
            failed: true,
          }));
        } else {
          setError(detail);
          patchAssistant(id, (m) => ({
            text: m.text || detail,
            streaming: false,
            failed: true,
          }));
        }
        setStreaming(false);
        es.close();
        esRef.current = null;
      }
    };

    es.onerror = () => {
      const id = assistantIdRef.current;

      if (esRef.current === es) {
        if (!predictComplete) {
          setPipelineAlert(true);
        } else if (id) {
          patchAssistant(id, (m) => {
            if (m.streaming && !m.text) {
              return {
                text: "Connection lost before an answer arrived. Try again.",
                streaming: false,
                failed: true,
              };
            }
            return { streaming: false };
          });
        }
        setStreaming(false);
        es.close();
        esRef.current = null;
      }
    };
  }, [input, streaming, predictComplete, patchAssistant]);

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  return (
    <DashboardLayout>
      <DashboardNavbar />
      <MDBox py={3} display="flex" flexDirection="column" sx={{ minHeight: "70vh" }}>
        <MDBox mb={3} px={0.5}>
          <MDTypography variant="h4" fontWeight="bold">
            Ask AI
          </MDTypography>
          <MDTypography variant="button" color="text">
            RAG-powered answers from your EFL resource library
          </MDTypography>
        </MDBox>
        {pipelineAlert && (
          <MDBox mb={2}>
            <MDAlert color="warning">
              <MDBox display="flex" flexDirection="column" gap={1} width="100%">
                <MDTypography variant="button" color="white">
                  The indexing pipeline hasn&apos;t finished yet — visit Pipeline Monitor to run it.
                </MDTypography>
                <MDBox>
                  <MDButton
                    component={RouterLink}
                    to="/pipeline/discover"
                    variant="outlined"
                    color="white"
                    size="small"
                  >
                    Open Pipeline Monitor
                  </MDButton>
                </MDBox>
              </MDBox>
            </MDAlert>
          </MDBox>
        )}

        {configAlert && (
          <MDBox mb={2}>
            <MDAlert color="error">
              AI answering isn&apos;t configured yet — add ANTHROPIC_API_KEY to backend/.env
            </MDAlert>
          </MDBox>
        )}

        {error && (
          <MDBox mb={2}>
            <MDAlert color="error">{error}</MDAlert>
          </MDBox>
        )}

        <Card
          sx={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            minHeight: "24rem",
            mb: 2,
          }}
        >
          <MDBox
            ref={listRef}
            flex={1}
            p={2}
            sx={{ overflowY: "auto", maxHeight: "calc(70vh - 8rem)" }}
          >
            {messages.length === 0 && (
              <WelcomeGuide
                disabled={!predictComplete || streaming}
                onPickExample={(example) => {
                  setInput(example);
                }}
              />
            )}

            {messages.map((msg) => {
              const isUser = msg.role === "user";
              return (
                <MDBox
                  key={msg.id}
                  display="flex"
                  justifyContent={isUser ? "flex-end" : "flex-start"}
                  mb={1.5}
                >
                  <MDBox
                    maxWidth={{ xs: "96%", md: !isUser && msg.sources ? "94%" : "75%" }}
                    px={1.75}
                    py={1.25}
                    borderRadius="lg"
                    sx={
                      isUser
                        ? {
                            backgroundColor: colors.primary.main,
                            color: colors.white.main,
                          }
                        : {
                            backgroundColor: colors.white.main,
                            border: `1px solid ${colors.grey[300]}`,
                          }
                    }
                  >
                    <MDTypography
                      variant="body2"
                      sx={{
                        whiteSpace: "pre-wrap",
                        color: isUser ? colors.white.main : colors.text.main,
                      }}
                    >
                      {msg.text || (msg.streaming ? "…" : "")}
                    </MDTypography>
                    {!isUser && msg.sources && (
                      <AssistantSources sources={msg.sources} onOpenSource={setPreviewId} />
                    )}
                  </MDBox>
                </MDBox>
              );
            })}
          </MDBox>

          <MDBox
            p={2}
            display="flex"
            gap={1}
            alignItems="flex-end"
            sx={{ borderTop: `1px solid ${colors.grey[300]}` }}
          >
            <MDBox flex={1}>
              <MDInput
                multiline
                minRows={2}
                maxRows={6}
                fullWidth
                label="Your question"
                placeholder={
                  predictComplete
                    ? "Ask about CEFR levels, topics, skills…"
                    : "Pipeline must finish Predict first"
                }
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={!predictComplete || streaming}
              />
            </MDBox>
            <MDButton
              variant="gradient"
              color="primary"
              onClick={handleSend}
              disabled={!predictComplete || streaming || !input.trim()}
            >
              Send
            </MDButton>
          </MDBox>
        </Card>
      </MDBox>

      <DocumentPreviewModal
        open={Boolean(previewId)}
        resourceId={previewId}
        onClose={() => setPreviewId(null)}
      />

      <Footer />
    </DashboardLayout>
  );
}

export default AskAI;
