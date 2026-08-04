import { useEffect, useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";

import Card from "@mui/material/Card";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDAlert from "components/MDAlert";
import MDButton from "components/MDButton";

import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";

import {
  CefrBadge,
  TagBadge,
  RecommendationsRail,
  DocumentPreviewModal,
} from "components/EflShared";
import { getResourceDetail } from "services/endpoints";
import colors from "assets/theme/base/colors";

const CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];

function RecommendationsPage() {
  const { resourceId } = useParams();
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [previewId, setPreviewId] = useState(null);

  useEffect(() => {
    if (!resourceId) {
      setError("Missing resource id");
      setLoading(false);
      return undefined;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getResourceDetail(resourceId);
        if (!cancelled) setDetail(data);
      } catch (err) {
        if (cancelled) return;
        const detailMsg = err?.response?.data?.detail || err?.message || "Failed to load resource";
        setError(typeof detailMsg === "string" ? detailMsg : JSON.stringify(detailMsg));
        setDetail(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [resourceId]);

  const cefrOk = detail?.cefr_level && CEFR_LEVELS.includes(detail.cefr_level);

  return (
    <DashboardLayout>
      <DashboardNavbar />
      <MDBox py={3}>
        <MDTypography variant="h4" fontWeight="bold" mb={0.5}>
          Recommendations
        </MDTypography>
        <MDTypography variant="button" color="text" mb={3} display="block">
          Related resources for a selected document
        </MDTypography>

        {error && (
          <MDBox mb={2}>
            <MDAlert color="error">{error}</MDAlert>
          </MDBox>
        )}

        {loading && (
          <MDTypography variant="button" color="text">
            Loading resource…
          </MDTypography>
        )}

        {!loading && detail && (
          <Card sx={{ p: 2, mb: 3 }}>
            <MDBox
              display="flex"
              flexWrap="wrap"
              justifyContent="space-between"
              alignItems="flex-start"
              gap={2}
              mb={2}
            >
              <MDBox flex={1} minWidth={0}>
                <MDTypography variant="h5" fontWeight="medium" mb={1}>
                  {detail.title}
                </MDTypography>
                <MDBox display="flex" flexWrap="wrap" gap={0.75} mb={1} alignItems="center">
                  {cefrOk && <CefrBadge level={detail.cefr_level} />}
                  {detail.skill_type && <TagBadge text={detail.skill_type} variant="skill" />}
                  {detail.topic_domain && <TagBadge text={detail.topic_domain} variant="topic" />}
                </MDBox>
                <MDTypography variant="caption" color="text" display="block">
                  {detail.resource_id}
                </MDTypography>
                {detail.source_name && (
                  <MDTypography variant="caption" display="block" sx={{ color: colors.text.focus }}>
                    Source: {detail.source_name}
                  </MDTypography>
                )}
              </MDBox>
              <MDBox display="flex" flexDirection="column" gap={1}>
                <MDButton
                  variant="gradient"
                  color="primary"
                  size="small"
                  onClick={() => setPreviewId(detail.resource_id)}
                >
                  Preview
                </MDButton>
                <MDButton
                  component={RouterLink}
                  to="/resources"
                  variant="outlined"
                  color="secondary"
                  size="small"
                >
                  Browse catalogue
                </MDButton>
              </MDBox>
            </MDBox>
            <MDTypography variant="body2" color="text" sx={{ lineHeight: 1.6 }}>
              {detail.raw_text_preview || "No preview available."}
            </MDTypography>
          </Card>
        )}

        {resourceId && !error && (
          <Card sx={{ p: 2 }}>
            <RecommendationsRail
              resourceId={resourceId}
              topK={8}
              onSelectResource={(id) => setPreviewId(id)}
            />
          </Card>
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

export default RecommendationsPage;
