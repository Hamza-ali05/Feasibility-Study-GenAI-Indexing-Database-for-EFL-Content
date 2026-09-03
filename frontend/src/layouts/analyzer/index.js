import { useCallback, useMemo, useRef, useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";

import Card from "@mui/material/Card";
import Tabs from "@mui/material/Tabs";
import Tab from "@mui/material/Tab";
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Icon from "@mui/material/Icon";
import CircularProgress from "@mui/material/CircularProgress";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDInput from "components/MDInput";
import MDButton from "components/MDButton";
import MDAlert from "components/MDAlert";

import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";

import { CefrBadge, TagBadge, LiveIndicator } from "components/EflShared";
import DocumentPreviewModal from "components/EflShared/DocumentPreviewModal";

import { usePipeline } from "context/PipelineContext";
import { uploadResource, confirmDuplicateUpload, patchResourceLabels } from "services/endpoints";
import colors from "assets/theme/base/colors";
import { SKILL_TYPES, TOPIC_DOMAINS } from "assets/theme/base/eflLabels";

const ANALYZER_STEPS = [
  { key: "clean", label: "Cleaning text" },
  { key: "classify", label: "Classifying" },
  { key: "embed", label: "Embedding" },
  { key: "duplicate_check", label: "Checking duplicates" },
  { key: "index", label: "Indexing" },
];

const ACCEPT = ".txt,.csv,.pdf";

function snippet(text, n = 220) {
  const cleaned = String(text || "")
    .replace(/\s+/g, " ")
    .trim();
  if (cleaned.length <= n) return cleaned;
  return `${cleaned.slice(0, n - 1)}…`;
}

function Analyzer() {
  const navigate = useNavigate();
  const { connected, analyzerStepsSeen, resetAnalyzerProgress } = usePipeline();

  const [tab, setTab] = useState(0);
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [pasteText, setPasteText] = useState("");
  const [title, setTitle] = useState("");

  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [pendingText, setPendingText] = useState("");

  const [manualSkill, setManualSkill] = useState("");
  const [manualTopic, setManualTopic] = useState("");
  const [savingLabels, setSavingLabels] = useState(false);
  const [labelsSaved, setLabelsSaved] = useState(false);

  const [previewId, setPreviewId] = useState(null);
  const fileInputRef = useRef(null);

  const completedKeys = useMemo(() => {
    const seen = new Set(analyzerStepsSeen || []);
    if (seen.has("indexed") || seen.has("duplicate_blocked")) {
      seen.add("index");
    }
    return seen;
  }, [analyzerStepsSeen]);

  const resetOutcome = () => {
    setResult(null);
    setError(null);
    setLabelsSaved(false);
    setManualSkill("");
    setManualTopic("");
  };

  const applyResult = (data) => {
    setResult(data);
    if (data?.classify_manually) {
      setManualSkill(data.skill_type || "");
      setManualTopic(data.topic_domain || "");
    }
  };

  const handleFiles = (fileList) => {
    const next = fileList && fileList[0] ? fileList[0] : null;
    if (!next) return;
    const lower = next.name.toLowerCase();
    if (!/\.(txt|csv|pdf)$/.test(lower)) {
      setError("Only .txt, .csv, and .pdf files are accepted.");
      return;
    }
    setFile(next);
    setError(null);
  };

  const buildPayload = useCallback(
    async (force) => {
      const titleForDup = title.trim() || null;
      if (tab === 0) {
        if (!file) throw new Error("Choose a .txt, .csv, or .pdf file to upload.");
        const fd = new FormData();
        fd.append("file", file);
        if (titleForDup) fd.append("title", titleForDup);
        if (force) fd.append("force", "true");
        return { body: fd, textPreview: `Uploaded file: ${file.name}` };
      }
      const text = pasteText.trim();
      if (!text) throw new Error("Paste some resource text first.");
      return {
        body: { text, title: titleForDup, force: Boolean(force) },
        textPreview: text,
      };
    },
    [tab, file, pasteText, title]
  );

  const runUpload = useCallback(
    async (force = false) => {
      resetOutcome();
      resetAnalyzerProgress();
      setProcessing(true);
      try {
        const { body, textPreview } = await buildPayload(force);
        setPendingText(textPreview);
        const data = await uploadResource(body);
        applyResult(data);
      } catch (err) {
        const status = err?.response?.status;
        const detail = err?.response?.data?.detail || err?.message || "Upload failed";
        setError(typeof detail === "string" ? detail : JSON.stringify(detail));
        if (status === 503) {
        }
      } finally {
        setProcessing(false);
      }
    },
    [buildPayload, resetAnalyzerProgress]
  );

  const handleForceKeep = async () => {
    if (tab === 1 && pasteText.trim()) {
      setProcessing(true);
      setError(null);
      resetAnalyzerProgress();
      try {
        const data = await confirmDuplicateUpload({
          text: pasteText.trim(),
          title: title.trim() || null,
          force: true,
        });
        applyResult(data);
      } catch (err) {
        const detail = err?.response?.data?.detail || err?.message || "Confirm failed";
        setError(typeof detail === "string" ? detail : JSON.stringify(detail));
      } finally {
        setProcessing(false);
      }
      return;
    }
    await runUpload(true);
  };

  const handleSaveLabels = async () => {
    if (!result?.resource_id) return;
    if (!manualSkill && !manualTopic) {
      setError("Select skill type and/or topic domain before saving.");
      return;
    }
    setSavingLabels(true);
    setError(null);
    try {
      const updated = await patchResourceLabels(result.resource_id, {
        skill_type: manualSkill || undefined,
        topic_domain: manualTopic || undefined,
      });
      setResult((prev) => ({
        ...prev,
        skill_type: updated.skill_type,
        topic_domain: updated.topic_domain,
        classify_manually: false,
      }));
      setLabelsSaved(true);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Save failed";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setSavingLabels(false);
    }
  };

  const isDuplicate = result && result.indexed === false && result.duplicate_of;
  const isSuccess = result && result.indexed === true;

  return (
    <DashboardLayout>
      <DashboardNavbar />
      <MDBox py={3}>
        <MDBox
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          flexWrap="wrap"
          gap={1}
          mb={2}
        >
          <MDBox>
            <MDTypography variant="h4" fontWeight="bold">
              AI Resource Analyzer
            </MDTypography>
            <MDTypography variant="button" color="text">
              Clean, classify, embed, and index a single resource live
            </MDTypography>
          </MDBox>
          <LiveIndicator connected={connected} />
        </MDBox>

        <Card sx={{ mb: 3 }}>
          <Tabs
            value={tab}
            onChange={(_, v) => {
              setTab(v);
              resetOutcome();
            }}
            textColor="primary"
            indicatorColor="primary"
            sx={{ borderBottom: `1px solid ${colors.grey[300]}`, px: 1 }}
          >
            <Tab label="Upload File" />
            <Tab label="Paste Text" />
          </Tabs>

          <MDBox p={2}>
            <MDBox mb={2}>
              <MDInput
                label="Title (optional)"
                fullWidth
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={processing}
              />
            </MDBox>

            {tab === 0 ? (
              <MDBox
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  handleFiles(e.dataTransfer.files);
                }}
                onClick={() => fileInputRef.current && fileInputRef.current.click()}
                sx={{
                  border: `2px dashed ${dragOver ? colors.primary.main : colors.grey[300]}`,
                  borderRadius: "0.75rem",
                  backgroundColor: dragOver ? colors.grey[100] : colors.white.main,
                  p: 4,
                  textAlign: "center",
                  cursor: "pointer",
                }}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={ACCEPT}
                  hidden
                  onChange={(e) => handleFiles(e.target.files)}
                />
                <Icon sx={{ fontSize: 40, color: colors.text.focus, mb: 1 }}>upload_file</Icon>
                <MDTypography variant="button" fontWeight="medium" display="block">
                  Drag & drop a .txt / .csv / .pdf here, or click to browse
                </MDTypography>
                {file && (
                  <MDTypography variant="caption" color="text" display="block" mt={1}>
                    Selected: {file.name}
                  </MDTypography>
                )}
              </MDBox>
            ) : (
              <MDInput
                multiline
                minRows={8}
                fullWidth
                label="Resource text"
                placeholder="Paste the full text of an EFL resource…"
                value={pasteText}
                onChange={(e) => setPasteText(e.target.value)}
                disabled={processing}
              />
            )}

            <MDBox mt={2} display="flex" gap={1}>
              <MDButton
                variant="gradient"
                color="primary"
                onClick={() => runUpload(false)}
                disabled={processing}
              >
                {processing ? "Analyzing…" : "Analyze & Index"}
              </MDButton>
              {processing && <CircularProgress size={22} sx={{ alignSelf: "center" }} />}
            </MDBox>
          </MDBox>
        </Card>

        {(processing || analyzerStepsSeen.length > 0) && (
          <Card sx={{ mb: 3, p: 2 }}>
            <MDTypography variant="h6" mb={1.5}>
              Processing steps
            </MDTypography>
            <MDBox component="ul" m={0} p={0} sx={{ listStyle: "none" }}>
              {ANALYZER_STEPS.map((step) => {
                const done = completedKeys.has(step.key);
                return (
                  <MDBox
                    component="li"
                    key={step.key}
                    display="flex"
                    alignItems="center"
                    gap={1}
                    py={0.75}
                  >
                    <Icon
                      sx={{
                        color: done ? colors.success.main : colors.grey[500],
                        fontSize: "1.25rem",
                      }}
                    >
                      {done ? "check_circle" : "radio_button_unchecked"}
                    </Icon>
                    <MDTypography
                      variant="button"
                      fontWeight={done ? "medium" : "regular"}
                      sx={{ color: done ? colors.success.main : colors.text.focus }}
                    >
                      {step.label}
                    </MDTypography>
                  </MDBox>
                );
              })}
            </MDBox>
          </Card>
        )}

        {error && (
          <MDBox mb={2}>
            <MDAlert color="error">
              <MDBox>
                {error}
                {String(error).toLowerCase().includes("train") && (
                  <MDBox mt={1}>
                    <MDButton
                      component={RouterLink}
                      to="/pipeline/train"
                      variant="outlined"
                      color="white"
                      size="small"
                    >
                      Open Pipeline Monitor
                    </MDButton>
                  </MDBox>
                )}
              </MDBox>
            </MDAlert>
          </MDBox>
        )}

        {isDuplicate && (
          <Card sx={{ p: 2, mb: 3, border: `1px solid ${colors.warning.main}` }}>
            <MDTypography variant="h6" mb={1}>
              Near-duplicate detected
            </MDTypography>
            <MDTypography variant="button" color="text" mb={2} display="block">
              Similarity {Number(result.duplicate_similarity || 0).toFixed(3)} — this upload was not
              indexed.
            </MDTypography>
            <MDBox
              display="grid"
              gap={2}
              sx={{ gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}
            >
              <MDBox
                p={1.5}
                borderRadius="md"
                sx={{
                  backgroundColor: colors.grey[100],
                  border: `1px solid ${colors.grey[300]}`,
                }}
              >
                <MDTypography variant="caption" fontWeight="bold" color="text">
                  New upload
                </MDTypography>
                <MDTypography variant="button" display="block" mt={0.5}>
                  {result.title}
                </MDTypography>
                <MDTypography variant="caption" sx={{ color: colors.text.focus }}>
                  {snippet(pendingText)}
                </MDTypography>
              </MDBox>
              <MDBox
                p={1.5}
                borderRadius="md"
                sx={{
                  backgroundColor: colors.white.main,
                  border: `1px solid ${colors.grey[300]}`,
                }}
              >
                <MDTypography variant="caption" fontWeight="bold" color="text">
                  Existing match
                </MDTypography>
                <MDTypography variant="button" display="block" mt={0.5}>
                  {result.duplicate_title || result.duplicate_of}
                </MDTypography>
                <MDBox display="flex" gap={0.75} mt={0.75} alignItems="center">
                  {result.cefr_level &&
                    ["A1", "A2", "B1", "B2", "C1", "C2"].includes(result.cefr_level) && (
                      <CefrBadge level={result.cefr_level} />
                    )}
                  <MDButton
                    variant="text"
                    color="primary"
                    size="small"
                    onClick={() => setPreviewId(result.duplicate_of)}
                  >
                    Preview existing
                  </MDButton>
                </MDBox>
              </MDBox>
            </MDBox>
            <MDBox mt={2} display="flex" gap={1} flexWrap="wrap">
              <MDButton
                variant="gradient"
                color="warning"
                onClick={handleForceKeep}
                disabled={processing}
              >
                Keep separate anyway
              </MDButton>
              <MDButton
                variant="outlined"
                color="secondary"
                onClick={() => {
                  setResult(null);
                  resetAnalyzerProgress();
                }}
                disabled={processing}
              >
                Cancel
              </MDButton>
            </MDBox>
          </Card>
        )}

        {isSuccess && (
          <MDBox mb={3}>
            <MDAlert color="success">Indexed as {result.resource_id}</MDAlert>
            <Card sx={{ p: 2, mt: 2 }}>
              <MDTypography variant="h6" mb={1}>
                {result.title}
              </MDTypography>
              <MDBox display="flex" flexWrap="wrap" gap={0.75} mb={2} alignItems="center">
                {result.cefr_level &&
                  ["A1", "A2", "B1", "B2", "C1", "C2"].includes(result.cefr_level) && (
                    <CefrBadge level={result.cefr_level} />
                  )}
                {result.skill_type && <TagBadge text={result.skill_type} variant="skill" />}
                {result.topic_domain && <TagBadge text={result.topic_domain} variant="topic" />}
              </MDBox>

              {result.classify_manually && !labelsSaved && (
                <MDBox
                  mb={2}
                  p={1.5}
                  borderRadius="md"
                  sx={{ border: `1px solid ${colors.warning.main}` }}
                >
                  <MDTypography variant="button" fontWeight="medium" display="block" mb={1}>
                    Classifier could not determine skill / topic — set them manually
                  </MDTypography>
                  <MDBox display="flex" flexWrap="wrap" gap={2} mb={1.5}>
                    <FormControl size="small" sx={{ minWidth: 280, flex: "1 1 280px" }}>
                      <InputLabel id="manual-skill">Skill type</InputLabel>
                      <Select
                        labelId="manual-skill"
                        label="Skill type"
                        value={manualSkill}
                        onChange={(e) => setManualSkill(e.target.value)}
                      >
                        <MenuItem value="">
                          <em>Unset</em>
                        </MenuItem>
                        {SKILL_TYPES.map((s) => (
                          <MenuItem key={s} value={s}>
                            {s}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                    <FormControl size="small" sx={{ minWidth: 280, flex: "1 1 280px" }}>
                      <InputLabel id="manual-topic">Topic domain</InputLabel>
                      <Select
                        labelId="manual-topic"
                        label="Topic domain"
                        value={manualTopic}
                        onChange={(e) => setManualTopic(e.target.value)}
                      >
                        <MenuItem value="">
                          <em>Unset</em>
                        </MenuItem>
                        {TOPIC_DOMAINS.map((t) => (
                          <MenuItem key={t} value={t}>
                            {t}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </MDBox>
                  <MDButton
                    variant="gradient"
                    color="primary"
                    size="small"
                    onClick={handleSaveLabels}
                    disabled={savingLabels}
                  >
                    {savingLabels ? "Saving…" : "Save"}
                  </MDButton>
                </MDBox>
              )}

              {labelsSaved && (
                <MDBox mb={2}>
                  <MDAlert color="info">Labels saved</MDAlert>
                </MDBox>
              )}

              <MDBox display="flex" gap={1} flexWrap="wrap">
                <MDButton
                  variant="gradient"
                  color="primary"
                  onClick={() => setPreviewId(result.resource_id)}
                >
                  Preview
                </MDButton>
                <MDButton
                  variant="outlined"
                  color="primary"
                  onClick={() => navigate(`/search?q=${encodeURIComponent(result.title || "")}`)}
                >
                  Search for it
                </MDButton>
              </MDBox>
            </Card>
          </MDBox>
        )}
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

export default Analyzer;
