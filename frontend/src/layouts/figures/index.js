/**
 * Dissertation Figures — generate and download Phase 13 diagrams.
 */

import { useCallback, useEffect, useState } from "react";

import Card from "@mui/material/Card";
import CircularProgress from "@mui/material/CircularProgress";
import Grid from "@mui/material/Grid";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDAlert from "components/MDAlert";
import MDButton from "components/MDButton";

import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";

import { exportDissertationFigures, listDissertationFigures } from "services/endpoints";
import { API_URL } from "services/apiClient";
import colors from "assets/theme/base/colors";

const TITLES = {
  system_architecture: "System Architecture",
  data_flow_diagram: "Data Flow Diagram",
  pipeline_flowchart: "Pipeline Flowchart",
  embedding_pipeline: "Embedding Pipeline",
  search_sequence: "Search Sequence",
  rag_sequence: "RAG Sequence",
  component_diagram: "Component Diagram",
  cefr_classification_flow: "CEFR Classification Flow",
};

function FiguresPage() {
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listDissertationFigures();
      setFiles(data.files || []);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Failed to list figures";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleExport = async () => {
    setBusy(true);
    setError(null);
    try {
      await exportDissertationFigures();
      await refresh();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Export failed";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setBusy(false);
    }
  };

  const pngs = files.filter((f) => f.format === "png");

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
              Dissertation Figures
            </MDTypography>
            <MDTypography variant="button" color="text">
              Architecture, DFD, pipeline, sequence, and classification diagrams (PNG + SVG).
            </MDTypography>
          </MDBox>
          <MDBox display="flex" gap={1}>
            <MDButton variant="gradient" color="primary" onClick={handleExport} disabled={busy}>
              {busy ? "Generating…" : "Generate All Figures"}
            </MDButton>
            <MDButton variant="text" color="info" onClick={refresh} disabled={loading}>
              Refresh
            </MDButton>
          </MDBox>
        </MDBox>

        {error && (
          <MDBox mb={2}>
            <MDAlert color="error">{error}</MDAlert>
          </MDBox>
        )}

        {loading ? (
          <MDBox py={4} display="flex" justifyContent="center">
            <CircularProgress />
          </MDBox>
        ) : !pngs.length ? (
          <Card sx={{ p: 3 }}>
            <MDTypography variant="button" color="text">
              No figures yet. Click Generate All Figures (admin JWT required).
            </MDTypography>
          </Card>
        ) : (
          <Grid container spacing={2}>
            {pngs.map((f) => {
              const svg = files.find((x) => x.stem === f.stem && x.format === "svg");
              const title = TITLES[f.stem] || f.stem;
              return (
                <Grid item xs={12} md={6} key={f.filename}>
                  <Card sx={{ p: 2, height: "100%" }}>
                    <MDTypography variant="h6" fontWeight="medium" mb={1}>
                      {title}
                    </MDTypography>
                    <MDBox
                      component="img"
                      src={`${API_URL}${f.download_url}`}
                      alt={title}
                      sx={{
                        width: "100%",
                        maxHeight: 280,
                        objectFit: "contain",
                        background: "#F9F8F5",
                        border: `1px solid ${colors.grey?.[200] || "#D3D1C7"}`,
                        borderRadius: 1,
                        mb: 1,
                      }}
                    />
                    <MDBox display="flex" gap={1} flexWrap="wrap">
                      <MDButton
                        size="small"
                        variant="outlined"
                        color="dark"
                        component="a"
                        href={`${API_URL}${f.download_url}`}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Download PNG
                      </MDButton>
                      {svg && (
                        <MDButton
                          size="small"
                          variant="text"
                          color="info"
                          component="a"
                          href={`${API_URL}${svg.download_url}`}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          Download SVG
                        </MDButton>
                      )}
                    </MDBox>
                    <MDTypography variant="caption" color="text" display="block" mt={1}>
                      {Math.round((f.size || 0) / 1024)} KB · {f.last_modified}
                    </MDTypography>
                  </Card>
                </Grid>
              );
            })}
          </Grid>
        )}
      </MDBox>
      <Footer />
    </DashboardLayout>
  );
}

export default FiguresPage;
