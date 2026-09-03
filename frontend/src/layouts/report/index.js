/**
 * Research Report Generator — admin page for dissertation draft sections.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import Card from "@mui/material/Card";
import Checkbox from "@mui/material/Checkbox";
import FormControlLabel from "@mui/material/FormControlLabel";
import FormGroup from "@mui/material/FormGroup";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDAlert from "components/MDAlert";
import MDButton from "components/MDButton";

import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";

import {
  downloadAllReportSections,
  generateResearchReport,
  getReportSection,
  listReportSections,
} from "services/endpoints";
import { API_URL } from "services/apiClient";
import colors from "assets/theme/base/colors";

const SECTION_OPTIONS = [
  { key: "results", label: "Results (Chapter 4)" },
  { key: "evaluation", label: "Evaluation (Chapter 5)" },
  { key: "methodology", label: "Methodology (Chapter 3)" },
  { key: "model_statistics", label: "Model Statistics (Appendix)" },
];

/** Minimal markdown → HTML (no external dependency). */
function markdownToHtml(md) {
  if (!md) return "";
  const escape = (s) =>
    String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  const lines = String(md).replace(/\r\n/g, "\n").split("\n");
  const html = [];
  let inUl = false;
  let inOl = false;
  let inCode = false;
  let inTable = false;
  let codeBuf = [];

  const closeLists = () => {
    if (inUl) {
      html.push("</ul>");
      inUl = false;
    }
    if (inOl) {
      html.push("</ol>");
      inOl = false;
    }
  };

  const closeTable = () => {
    if (inTable) {
      html.push("</tbody></table>");
      inTable = false;
    }
  };

  const inline = (text) => {
    let t = escape(text);
    t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
    t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    t = t.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    t = t.replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
    );
    return t;
  };

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];

    if (line.trim().startsWith("```")) {
      if (inCode) {
        html.push(`<pre><code>${escape(codeBuf.join("\n"))}</code></pre>`);
        codeBuf = [];
        inCode = false;
      } else {
        closeLists();
        closeTable();
        inCode = true;
      }
      continue;
    }
    if (inCode) {
      codeBuf.push(line);
      continue;
    }

    if (/^\|(.+)\|$/.test(line.trim()) || (line.includes("|") && line.trim().startsWith("|"))) {
      const cells = line
        .trim()
        .replace(/^\|/, "")
        .replace(/\|$/, "")
        .split("|")
        .map((c) => c.trim());
      const isSep = cells.every((c) => /^:?-{3,}:?$/.test(c));
      if (isSep) {
        continue;
      }
      if (!inTable) {
        closeLists();
        html.push('<table style="width:100%;border-collapse:collapse;margin:0.75rem 0"><thead>');
        html.push(
          `<tr>${cells
            .map(
              (c) =>
                `<th style="border:1px solid #D3D1C7;padding:6px 8px;text-align:left;background:#EEEDFE">${inline(
                  c
                )}</th>`
            )
            .join("")}</tr></thead><tbody>`
        );
        inTable = true;
      } else {
        html.push(
          `<tr>${cells
            .map(
              (c) =>
                `<td style="border:1px solid #D3D1C7;padding:6px 8px;vertical-align:top">${inline(
                  c
                )}</td>`
            )
            .join("")}</tr>`
        );
      }
      continue;
    }
    closeTable();

    if (/^###\s+/.test(line)) {
      closeLists();
      html.push(`<h3>${inline(line.replace(/^###\s+/, ""))}</h3>`);
      continue;
    }
    if (/^##\s+/.test(line)) {
      closeLists();
      html.push(`<h2>${inline(line.replace(/^##\s+/, ""))}</h2>`);
      continue;
    }
    if (/^#\s+/.test(line)) {
      closeLists();
      html.push(`<h1>${inline(line.replace(/^#\s+/, ""))}</h1>`);
      continue;
    }
    if (/^[-*]\s+/.test(line)) {
      if (!inUl) {
        closeLists();
        html.push("<ul>");
        inUl = true;
      }
      html.push(`<li>${inline(line.replace(/^[-*]\s+/, ""))}</li>`);
      continue;
    }
    if (/^\d+\.\s+/.test(line)) {
      if (!inOl) {
        closeLists();
        html.push("<ol>");
        inOl = true;
      }
      html.push(`<li>${inline(line.replace(/^\d+\.\s+/, ""))}</li>`);
      continue;
    }
    if (!line.trim()) {
      closeLists();
      continue;
    }
    closeLists();
    html.push(`<p>${inline(line)}</p>`);
  }

  closeLists();
  closeTable();
  if (inCode) {
    html.push(`<pre><code>${escape(codeBuf.join("\n"))}</code></pre>`);
  }
  return html.join("\n");
}

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return String(iso);
  }
}

function ReportGenerator() {
  const [selected, setSelected] = useState({
    results: true,
    evaluation: true,
    methodology: true,
    model_statistics: true,
  });
  const [sections, setSections] = useState([]);
  const [readiness, setReadiness] = useState([]);
  const [busy, setBusy] = useState(false);
  const [loadingList, setLoadingList] = useState(true);
  const [error, setError] = useState(null);
  const [preview, setPreview] = useState(null);
  const [previewHtml, setPreviewHtml] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);

  const allSelected = useMemo(() => SECTION_OPTIONS.every((o) => selected[o.key]), [selected]);

  const refresh = useCallback(async () => {
    setLoadingList(true);
    setError(null);
    try {
      const data = await listReportSections();
      setSections(data.sections || []);
      setReadiness(data.readiness || []);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Failed to load sections";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const toggle = (key) => {
    setSelected((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleAll = () => {
    const next = !allSelected;
    setSelected({
      results: next,
      evaluation: next,
      methodology: next,
      model_statistics: next,
    });
  };

  const handleGenerate = async () => {
    const keys = SECTION_OPTIONS.filter((o) => selected[o.key]).map((o) => o.key);
    if (!keys.length) {
      setError("Select at least one section.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await generateResearchReport(keys);
      await refresh();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Generation failed";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setBusy(false);
    }
  };

  const handlePreview = async (filename) => {
    setPreviewLoading(true);
    setError(null);
    try {
      const data = await getReportSection(filename);
      setPreview(data);
      setPreviewHtml(markdownToHtml(data.content || ""));
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Preview failed";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleDownloadAll = async () => {
    setBusy(true);
    setError(null);
    try {
      const blob = await downloadAllReportSections();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "draft_chapters.zip";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Download failed";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setBusy(false);
    }
  };

  return (
    <DashboardLayout>
      <DashboardNavbar />
      <MDBox py={3}>
        <MDTypography variant="h4" fontWeight="bold" mb={1}>
          Research Report Generator
        </MDTypography>
        <MDTypography variant="button" color="text" mb={2} display="block">
          Auto-draft dissertation chapters from pipeline, evaluation, and practitioner artefacts
          (admin JWT required).
        </MDTypography>

        {error && (
          <MDBox mb={2}>
            <MDAlert color="error">{error}</MDAlert>
          </MDBox>
        )}

        <Card sx={{ p: 2, mb: 2 }}>
          <MDTypography variant="h6" fontWeight="medium" mb={1}>
            Data Readiness
          </MDTypography>
          <MDBox component="ul" sx={{ m: 0, pl: 2 }}>
            {(readiness.length ? readiness : []).map((item) => (
              <MDBox component="li" key={item.id} mb={0.5}>
                <MDTypography variant="button" color="text">
                  {item.ready ? "✅" : "❌"} {item.label}{" "}
                  {!item.ready && item.link && (
                    <MDTypography
                      component={Link}
                      to={item.link}
                      variant="caption"
                      sx={{ color: colors.info.main, ml: 1 }}
                    >
                      Complete this →
                    </MDTypography>
                  )}
                </MDTypography>
              </MDBox>
            ))}
            {!readiness.length && !loadingList && (
              <MDTypography variant="caption" color="text">
                Readiness checklist unavailable.
              </MDTypography>
            )}
          </MDBox>
        </Card>

        <Card sx={{ p: 2, mb: 2 }}>
          <MDTypography variant="h6" fontWeight="medium" mb={1}>
            Sections to generate
          </MDTypography>
          <FormGroup>
            <FormControlLabel
              control={<Checkbox checked={allSelected} onChange={toggleAll} />}
              label="Select All"
            />
            {SECTION_OPTIONS.map((opt) => (
              <FormControlLabel
                key={opt.key}
                control={
                  <Checkbox checked={!!selected[opt.key]} onChange={() => toggle(opt.key)} />
                }
                label={opt.label}
              />
            ))}
          </FormGroup>
          <MDBox mt={2} display="flex" gap={1} flexWrap="wrap">
            <MDButton variant="gradient" color="primary" onClick={handleGenerate} disabled={busy}>
              {busy ? "Working…" : "Generate Selected"}
            </MDButton>
            <MDButton
              variant="outlined"
              color="dark"
              onClick={handleDownloadAll}
              disabled={busy || !sections.length}
            >
              Download All (.zip)
            </MDButton>
            <MDButton variant="text" color="info" onClick={refresh} disabled={loadingList}>
              Refresh list
            </MDButton>
          </MDBox>
        </Card>

        <Card sx={{ p: 2, mb: 2 }}>
          <MDTypography variant="h6" fontWeight="medium" mb={1}>
            Generated sections
          </MDTypography>
          {loadingList && (
            <MDBox display="flex" alignItems="center" gap={1}>
              <CircularProgress size={18} />
              <MDTypography variant="caption">Loading…</MDTypography>
            </MDBox>
          )}
          {!loadingList && !sections.length && (
            <MDTypography variant="caption" color="text">
              No drafts yet. Select sections and click Generate Selected.
            </MDTypography>
          )}
          {sections.map((sec) => (
            <MDBox
              key={sec.filename}
              display="flex"
              justifyContent="space-between"
              alignItems="center"
              flexWrap="wrap"
              gap={1}
              py={1.5}
              sx={{ borderBottom: `1px solid ${colors.grey?.[200] || "#D3D1C7"}` }}
            >
              <MDBox>
                <MDTypography variant="button" fontWeight="medium">
                  {sec.title || sec.filename}
                </MDTypography>
                <MDTypography variant="caption" color="text" display="block">
                  {sec.word_count} words · {Math.round((sec.size || 0) / 1024)} KB ·{" "}
                  {fmtDate(sec.last_modified)}
                </MDTypography>
              </MDBox>
              <MDBox display="flex" gap={1}>
                <MDButton
                  size="small"
                  variant="outlined"
                  color="info"
                  onClick={() => handlePreview(sec.filename)}
                  disabled={previewLoading}
                >
                  Preview
                </MDButton>
                <MDButton
                  size="small"
                  variant="text"
                  color="dark"
                  component="a"
                  href={`${API_URL}${
                    sec.download_url || `/static/research-reports/draft_chapters/${sec.filename}`
                  }`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Download .md
                </MDButton>
              </MDBox>
            </MDBox>
          ))}
        </Card>

        {(preview || previewLoading) && (
          <Card sx={{ p: 2 }}>
            <MDBox display="flex" justifyContent="space-between" alignItems="center" mb={1}>
              <MDTypography variant="h6" fontWeight="medium">
                Preview{preview ? `: ${preview.title || preview.filename}` : ""}
              </MDTypography>
              {preview && (
                <MDButton size="small" color="secondary" onClick={() => setPreview(null)}>
                  Close
                </MDButton>
              )}
            </MDBox>
            <Divider />
            {previewLoading ? (
              <MDBox py={3} display="flex" justifyContent="center">
                <CircularProgress size={28} />
              </MDBox>
            ) : (
              <MDBox
                mt={2}
                sx={{
                  maxHeight: "70vh",
                  overflow: "auto",
                  color: colors.dark?.main || "#2C2C2A",
                  "& h1": { fontSize: "1.5rem", marginTop: "1rem" },
                  "& h2": { fontSize: "1.25rem", marginTop: "1rem" },
                  "& h3": { fontSize: "1.1rem", marginTop: "0.75rem" },
                  "& p, & li": { fontSize: "0.9rem", lineHeight: 1.55 },
                  "& code": {
                    background: "#EEEDFE",
                    padding: "0 4px",
                    borderRadius: 2,
                    fontSize: "0.85em",
                  },
                  "& pre": {
                    background: "#F9F8F5",
                    border: "1px solid #D3D1C7",
                    padding: "0.75rem",
                    overflow: "auto",
                  },
                }}
                dangerouslySetInnerHTML={{ __html: previewHtml }}
              />
            )}
          </Card>
        )}
      </MDBox>
      <Footer />
    </DashboardLayout>
  );
}

export default ReportGenerator;
