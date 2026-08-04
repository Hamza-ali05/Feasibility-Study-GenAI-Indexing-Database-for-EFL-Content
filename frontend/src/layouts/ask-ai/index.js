import { useCallback, useEffect, useRef, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import PropTypes from "prop-types";

import Card from "@mui/material/Card";
import Collapse from "@mui/material/Collapse";
import IconButton from "@mui/material/IconButton";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";

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

function AssistantSources({ sources, onOpenSource }) {
  const [open, setOpen] = useState(false);
  if (!sources || sources.length === 0) return null;

  return (
    <MDBox mt={1.25}>
      <MDBox
        display="flex"
        alignItems="center"
        sx={{ cursor: "pointer" }}
        onClick={() => setOpen((v) => !v)}
      >
        <MDTypography variant="caption" fontWeight="bold" color="text">
          Sources ({sources.length})
        </MDTypography>
        <IconButton size="small" aria-label={open ? "Hide sources" : "Show sources"}>
          {open ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
        </IconButton>
      </MDBox>
      <Collapse in={open}>
        <MDBox component="ul" m={0} mt={0.5} pl={0} sx={{ listStyle: "none" }}>
          {sources.map((src) => {
            const cefrOk =
              src.cefr_level && ["A1", "A2", "B1", "B2", "C1", "C2"].includes(src.cefr_level);
            return (
              <MDBox
                component="li"
                key={src.resource_id}
                display="flex"
                alignItems="center"
                gap={1}
                py={0.5}
                sx={{
                  cursor: "pointer",
                  "&:hover .src-title": { textDecoration: "underline" },
                }}
                onClick={() => onOpenSource(src.resource_id)}
              >
                <MDTypography
                  className="src-title"
                  variant="caption"
                  fontWeight="medium"
                  sx={{ color: colors.primary.main }}
                >
                  {src.title}
                </MDTypography>
                {cefrOk && <CefrBadge level={src.cefr_level} />}
              </MDBox>
            );
          })}
        </MDBox>
      </Collapse>
    </MDBox>
  );
}

AssistantSources.propTypes = {
  sources: PropTypes.arrayOf(
    PropTypes.shape({
      resource_id: PropTypes.string,
      title: PropTypes.string,
      cefr_level: PropTypes.string,
    })
  ),
  onOpenSource: PropTypes.func.isRequired,
};

AssistantSources.defaultProps = {
  sources: [],
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
        <MDTypography variant="h4" fontWeight="bold" mb={0.5}>
          Ask AI
        </MDTypography>
        <MDTypography variant="button" color="text" mb={2} display="block">
          Question answering over your indexed EFL resources (RAG)
        </MDTypography>

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
              <MDTypography variant="button" color="text">
                Ask a question about your indexed EFL content. Answers stream live from the RAG
                service.
              </MDTypography>
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
                    maxWidth={{ xs: "92%", md: "75%" }}
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
                    {!isUser && !msg.streaming && msg.sources && (
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
