
import { useEffect, useState } from "react";
import PropTypes from "prop-types";

import Dialog from "@mui/material/Dialog";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import IconButton from "@mui/material/IconButton";
import CircularProgress from "@mui/material/CircularProgress";
import Link from "@mui/material/Link";
import Divider from "@mui/material/Divider";
import CloseIcon from "@mui/icons-material/Close";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDAlert from "components/MDAlert";

import CefrBadge from "components/EflShared/CefrBadge";
import TagBadge from "components/EflShared/TagBadge";
import RecommendationsRail from "components/EflShared/RecommendationsRail";
import { getResourceDetail, markResourceViewed } from "services/endpoints";
import colors from "assets/theme/base/colors";

function cefrValid(level) {
  return level && ["A1", "A2", "B1", "B2", "C1", "C2"].includes(level);
}

function paragraphsFromText(text) {
  const raw = text || "";
  const blocks = raw
    .replace(/\r\n/g, "\n")
    .split(/\n{2,}/)
    .map((b) => b.trim())
    .filter(Boolean);
  if (blocks.length === 0 && raw.trim()) {
    return [raw.trim()];
  }
  return blocks.length ? blocks : ["(No text available)"];
}

function DocumentPreviewModal({ resourceId, open, onClose }) {
  const [activeId, setActiveId] = useState(resourceId);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (open && resourceId) {
      setActiveId(resourceId);
    }
    if (!open) {
      setDetail(null);
      setError(null);
    }
  }, [open, resourceId]);

  useEffect(() => {
    if (!open || !activeId) {
      return undefined;
    }

    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      setDetail(null);

      markResourceViewed(activeId).catch(() => {});

      try {
        const data = await getResourceDetail(activeId);
        if (!cancelled) setDetail(data);
      } catch (err) {
        if (!cancelled) {
          const detailMsg =
            err?.response?.data?.detail || err?.message || "Failed to load resource";
          setError(typeof detailMsg === "string" ? detailMsg : JSON.stringify(detailMsg));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [open, activeId]);

  const bodyParagraphs = paragraphsFromText(
    detail?.raw_text_full || detail?.raw_text_preview || ""
  );

  return (
    <Dialog
      open={open}
      onClose={onClose}
      fullWidth
      maxWidth="lg"
      scroll="paper"
      PaperProps={{
        sx: { minHeight: { md: "70vh" } },
      }}
    >
      <DialogTitle sx={{ pr: 6 }}>
        <MDTypography variant="h5" fontWeight="bold" component="span">
          {detail?.title || (loading ? "Loading…" : "Document Preview")}
        </MDTypography>
        <IconButton
          aria-label="close"
          onClick={onClose}
          sx={{ position: "absolute", right: 8, top: 8 }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers>
        {loading && (
          <MDBox display="flex" justifyContent="center" py={6}>
            <CircularProgress size={32} />
          </MDBox>
        )}
        {error && <MDAlert color="error">{error}</MDAlert>}
        {!loading && detail && (
          <MDBox>
            <MDBox display="flex" flexWrap="wrap" gap={1} mb={1.5} alignItems="center">
              {cefrValid(detail.cefr_level) && <CefrBadge level={detail.cefr_level} />}
              {detail.skill_type && <TagBadge text={detail.skill_type} variant="skill" />}
              {detail.topic_domain && <TagBadge text={detail.topic_domain} variant="topic" />}
              {detail.source_name && <TagBadge text={detail.source_name} variant="source" />}
            </MDBox>

            <MDBox mb={2}>
              {detail.source_name && (
                <MDTypography variant="button" color="text" display="block">
                  Source: {detail.source_name}
                </MDTypography>
              )}
              {detail.source_url && (
                <Link
                  href={detail.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  underline="hover"
                  sx={{ color: colors.primary.main, fontSize: "0.875rem" }}
                >
                  {detail.source_url}
                </Link>
              )}
            </MDBox>

            <MDBox
              px={2.5}
              py={2}
              borderRadius="lg"
              sx={{
                backgroundColor: colors.grey[100],
                border: `1px solid ${colors.grey[300]}`,
                maxHeight: { xs: "40vh", md: "48vh" },
                overflowY: "auto",
              }}
            >
              {bodyParagraphs.map((para, idx) => (
                <MDTypography

                  key={idx}
                  variant="body2"
                  mb={idx < bodyParagraphs.length - 1 ? 1.5 : 0}
                  sx={{
                    color: colors.text.main,
                    whiteSpace: "pre-wrap",
                    lineHeight: 1.7,
                    fontFamily: "Georgia, 'Times New Roman', serif",
                  }}
                >
                  {para}
                </MDTypography>
              ))}
            </MDBox>

            <Divider sx={{ my: 2.5 }} />

            <RecommendationsRail resourceId={activeId} topK={4} onSelectResource={setActiveId} />
          </MDBox>
        )}
      </DialogContent>
    </Dialog>
  );
}

DocumentPreviewModal.propTypes = {
  resourceId: PropTypes.string,
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
};

DocumentPreviewModal.defaultProps = {
  resourceId: null,
};

export default DocumentPreviewModal;
