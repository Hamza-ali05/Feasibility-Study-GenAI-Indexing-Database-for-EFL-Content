
import { useRef, useState } from "react";
import PropTypes from "prop-types";

import Card from "@mui/material/Card";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDButton from "components/MDButton";

import CefrBadge from "components/EflShared/CefrBadge";
import TagBadge from "components/EflShared/TagBadge";
import SimilarityBar from "components/EflShared/SimilarityBar";
import RecommendationsRail from "components/EflShared/RecommendationsRail";
import colors from "assets/theme/base/colors";

function SearchResultCard({ result, onPreview }) {
  const [showRelated, setShowRelated] = useState(false);
  const hoverTimer = useRef(null);

  const cefrOk =
    result.cefr_level && ["A1", "A2", "B1", "B2", "C1", "C2"].includes(result.cefr_level);

  const openRelated = () => setShowRelated(true);

  const handleMouseEnter = () => {
    hoverTimer.current = setTimeout(() => {
      openRelated();
    }, 400);
  };

  const handleMouseLeave = () => {
    if (hoverTimer.current) {
      clearTimeout(hoverTimer.current);
      hoverTimer.current = null;
    }
  };

  return (
    <Card sx={{ mb: 2 }} onMouseEnter={handleMouseEnter} onMouseLeave={handleMouseLeave}>
      <MDBox p={2}>
        <MDBox display="flex" justifyContent="space-between" alignItems="flex-start" gap={2}>
          <MDBox flex={1} minWidth={0}>
            <MDTypography variant="h6" fontWeight="medium" mb={1}>
              {result.title}
            </MDTypography>
            <MDBox display="flex" flexWrap="wrap" gap={0.75} mb={1.5} alignItems="center">
              {cefrOk && <CefrBadge level={result.cefr_level} />}
              {result.skill_type && <TagBadge text={result.skill_type} variant="skill" />}
              {result.topic_domain && <TagBadge text={result.topic_domain} variant="topic" />}
            </MDBox>
            <MDBox mb={1} maxWidth="28rem">
              <SimilarityBar value={Number(result.similarity_score) || 0} />
            </MDBox>
            {result.source_name && (
              <MDTypography variant="caption" sx={{ color: colors.text.focus }}>
                Source: {result.source_name}
              </MDTypography>
            )}
          </MDBox>
          <MDBox display="flex" flexDirection="column" gap={1} flexShrink={0}>
            <MDButton
              variant="gradient"
              color="primary"
              size="small"
              onClick={() => onPreview(result.resource_id)}
            >
              Preview
            </MDButton>
            <MDButton
              variant="outlined"
              color="secondary"
              size="small"
              onClick={() => setShowRelated((v) => !v)}
            >
              {showRelated ? "Hide related" : "Related"}
            </MDButton>
          </MDBox>
        </MDBox>

        {showRelated && (
          <MDBox mt={2} pt={1.5} sx={{ borderTop: `1px solid ${colors.grey[300]}` }}>
            <RecommendationsRail
              resourceId={result.resource_id}
              topK={3}
              onSelectResource={onPreview}
            />
          </MDBox>
        )}
      </MDBox>
    </Card>
  );
}

SearchResultCard.propTypes = {
  result: PropTypes.shape({
    resource_id: PropTypes.string.isRequired,
    title: PropTypes.string.isRequired,
    cefr_level: PropTypes.string,
    skill_type: PropTypes.string,
    topic_domain: PropTypes.string,
    source_name: PropTypes.string,
    similarity_score: PropTypes.number,
  }).isRequired,
  onPreview: PropTypes.func.isRequired,
};

export default SearchResultCard;
