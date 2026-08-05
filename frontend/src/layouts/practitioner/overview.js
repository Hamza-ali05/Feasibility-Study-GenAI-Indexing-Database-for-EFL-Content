import { useCallback, useEffect, useMemo, useState } from "react";

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
import VerticalBarChart from "examples/Charts/BarCharts/VerticalBarChart";

import { MetricCard } from "components/EflShared";
import {
  exportPractitionerReports,
  getPractitionerRecruitmentSummary,
  getPractitionerReport,
  getPractitionerSusSummary,
  getPractitionerThematicSummary,
} from "services/endpoints";
import colors from "assets/theme/base/colors";

const RECRUITMENT_CARDS = [
  { key: "total_recruited", label: "Recruited" },
  { key: "total_consented", label: "Consented" },
  { key: "total_interviewed", label: "Interviewed" },
  { key: "total_transcribed", label: "Transcribed" },
  { key: "total_coded", label: "Coded" },
  { key: "total_withdrawn", label: "Withdrawn" },
];

function PractitionerOverview() {
  const [recruitment, setRecruitment] = useState(null);
  const [sus, setSus] = useState(null);
  const [thematic, setThematic] = useState(null);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [exportMsg, setExportMsg] = useState(null);
  const [exportError, setExportError] = useState(null);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [rec, susRes, them, full] = await Promise.all([
        getPractitionerRecruitmentSummary(),
        getPractitionerSusSummary(),
        getPractitionerThematicSummary(),
        getPractitionerReport(),
      ]);
      setRecruitment(rec);
      setSus(susRes);
      setThematic(them);
      setReport(full);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Failed to load";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const contextChart = useMemo(() => {
    const contexts = report?.demographics?.teaching_contexts || {};
    const labels = Object.keys(contexts);
    const data = labels.map((k) => Number(contexts[k]) || 0);
    return {
      labels: labels.length ? labels : ["No data"],
      datasets: [
        {
          label: "Participants",
          data: data.length ? data : [0],
          color: colors.info.main,
        },
      ],
    };
  }, [report]);

  const onExport = async () => {
    setExporting(true);
    setExportError(null);
    setExportMsg(null);
    try {
      const res = await exportPractitionerReports();
      const files = Array.isArray(res?.files) ? res.files : [];
      setExportMsg(
        files.length
          ? `Exported ${files.length} file(s) to ${res.output_dir}: ${files.join(", ")}`
          : `Export completed to ${res?.output_dir || "research/reports"} (no files listed).`
      );
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Export failed";
      setExportError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setExporting(false);
    }
  };

  return (
    <DashboardLayout>
      <DashboardNavbar hideBreadcrumbs />
      <MDBox py={3}>
        <MDBox
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          mb={2}
          flexWrap="wrap"
          gap={1}
        >
          <MDTypography variant="h4" fontWeight="bold">
            Practitioner Evaluation
          </MDTypography>
          <MDButton
            variant="gradient"
            color="primary"
            size="small"
            disabled={exporting || loading}
            onClick={onExport}
          >
            {exporting ? (
              <MDBox display="inline-flex" alignItems="center" gap={1}>
                <CircularProgress size={14} color="inherit" />
                Exporting…
              </MDBox>
            ) : (
              "Export All Reports"
            )}
          </MDButton>
        </MDBox>

        {error && (
          <MDBox mb={2}>
            <MDAlert color="error">{error}</MDAlert>
          </MDBox>
        )}
        {exportError && (
          <MDBox mb={2}>
            <MDAlert color="error">{exportError}</MDAlert>
          </MDBox>
        )}
        {exportMsg && (
          <MDBox mb={2}>
            <MDAlert color="success">{exportMsg}</MDAlert>
          </MDBox>
        )}

        {loading ? (
          <MDBox display="flex" justifyContent="center" py={6}>
            <CircularProgress color="info" />
          </MDBox>
        ) : (
          <>
            <MDTypography variant="h6" mb={1.5}>
              Recruitment progress
            </MDTypography>
            <Grid container spacing={2} mb={3}>
              {RECRUITMENT_CARDS.map(({ key, label }) => (
                <Grid item xs={12} sm={6} md={4} lg={2} key={key}>
                  <MetricCard label={label} value={String(recruitment?.[key] ?? 0)} />
                </Grid>
              ))}
            </Grid>

            <Grid container spacing={2} mb={3}>
              <Grid item xs={12} md={6}>
                <VerticalBarChart
                  icon={{ color: "info", component: "school" }}
                  title="Teaching context"
                  description="Active participants by teaching context"
                  height="14rem"
                  chart={contextChart}
                />
              </Grid>
              <Grid item xs={12} md={3}>
                <Card sx={{ height: "100%" }}>
                  <MDBox p={2}>
                    <MDTypography variant="button" color="text" fontWeight="light">
                      System Usability Scale
                    </MDTypography>
                    <MDTypography variant="h3" fontWeight="bold" mt={1}>
                      {sus?.mean_sus != null ? sus.mean_sus : "—"}
                    </MDTypography>
                    <MDTypography variant="button" color="text" mt={1} display="block">
                      Adjective: <strong>{sus?.adjective_rating || "n/a"}</strong>
                    </MDTypography>
                    <MDTypography variant="caption" color="text" display="block" mt={0.5}>
                      n = {sus?.n_respondents ?? 0}
                      {sus?.std_sus != null ? ` · SD ${sus.std_sus}` : ""}
                    </MDTypography>
                  </MDBox>
                </Card>
              </Grid>
              <Grid item xs={12} md={3}>
                <Card sx={{ height: "100%" }}>
                  <MDBox p={2}>
                    <MDTypography variant="button" color="text" fontWeight="light">
                      Thematic analysis
                    </MDTypography>
                    <MDTypography variant="h3" fontWeight="bold" mt={1}>
                      {String(thematic?.total_themes ?? 0)}
                    </MDTypography>
                    <MDTypography variant="button" color="text" mt={1} display="block">
                      Themes defined
                    </MDTypography>
                    <MDTypography variant="caption" color="text" display="block" mt={0.5}>
                      {thematic?.total_codes ?? 0} codes · {thematic?.total_segments ?? 0} segments
                    </MDTypography>
                  </MDBox>
                </Card>
              </Grid>
            </Grid>

            <Card sx={{ p: 2 }}>
              <MDTypography variant="h6" mb={1}>
                Mean experience
              </MDTypography>
              <MDTypography variant="body2" color="text">
                {recruitment?.mean_experience_years ?? 0} years (active practitioners). Contexts
                represented: {(recruitment?.contexts_represented || []).join(", ") || "none yet"}.
              </MDTypography>
            </Card>
          </>
        )}
      </MDBox>
      <Footer />
    </DashboardLayout>
  );
}

export default PractitionerOverview;
