import { useEffect, useState } from "react";
import PropTypes from "prop-types";

import Card from "@mui/material/Card";
import Skeleton from "@mui/material/Skeleton";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";

import CefrBadge from "components/EflShared/CefrBadge";
import SimilarityBar from "components/EflShared/SimilarityBar";
import { getRecommendations } from "services/endpoints";
import colors from "assets/theme/base/colors";

function cefrValid(level) {
  return level && ["A1", "A2", "B1", "B2", "C1", "C2"].includes(level);
}

function RecommendationsRail({ resourceId, topK, onSelectResource }) {
  const [items, setItems] = useState(null);
  const [loading, setLoading] = useState(false);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    if (!resourceId) {
      setHidden(true);
      return undefined;
    }

    let cancelled = false;
    setLoading(true);
    setHidden(false);
    setItems(null);

    (async () => {
      try {
        const data = await getRecommendations(resourceId, topK);
        if (cancelled) return;
        const list = Array.isArray(data?.recommendations) ? data.recommendations : [];
        setItems(list);
        if (list.length === 0) setHidden(true);
      } catch (err) {
        if (cancelled) return;

        setHidden(true);
        setItems(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [resourceId, topK]);

  if (hidden && !loading) return null;

  if (loading) {
    return (
      <MDBox>
        <MDTypography variant="h6" fontWeight="medium" mb={1.5}>
          Related Resources
        </MDTypography>
        <MDBox display="flex" gap={1.5} sx={{ overflowX: "auto", pb: 1 }}>
          {[0, 1, 2].map((i) => (
            <Card key={i} sx={{ minWidth: 200, p: 1.5, flexShrink: 0 }}>
              <Skeleton width="80%" height={22} />
              <Skeleton width="40%" height={18} sx={{ mt: 1 }} />
              <Skeleton width="100%" height={10} sx={{ mt: 1.5 }} />
              <Skeleton width="90%" height={14} sx={{ mt: 1 }} />
            </Card>
          ))}
        </MDBox>
      </MDBox>
    );
  }

  if (!items || items.length === 0) return null;

  return (
    <MDBox>
      <MDTypography variant="h6" fontWeight="medium" mb={1.5}>
        Related Resources
      </MDTypography>
      <MDBox
        display="flex"
        gap={1.5}
        sx={{
          overflowX: "auto",
          pb: 1,
          scrollSnapType: "x mandatory",
        }}
      >
        {items.map((item) => (
          <Card
            key={item.resource_id}
            sx={{
              minWidth: 220,
              maxWidth: 260,
              flexShrink: 0,
              p: 1.5,
              cursor: "pointer",
              scrollSnapAlign: "start",
              border: `1px solid ${colors.grey[300]}`,
              boxShadow: "none",
              "&:hover": {
                borderColor: colors.primary.main,
              },
            }}
            onClick={() => onSelectResource(item.resource_id)}
          >
            <MDTypography
              variant="button"
              fontWeight="medium"
              display="block"
              mb={0.75}
              sx={{
                color: colors.text.main,
                display: "-webkit-box",
                WebkitLineClamp: 2,
                WebkitBoxOrient: "vertical",
                overflow: "hidden",
              }}
            >
              {item.title}
            </MDTypography>
            {cefrValid(item.cefr_level) && (
              <MDBox mb={0.75}>
                <CefrBadge level={item.cefr_level} />
              </MDBox>
            )}
            <MDBox mb={0.75}>
              <SimilarityBar value={Number(item.similarity_score) || 0} />
            </MDBox>
            {item.reason && (
              <MDTypography
                variant="caption"
                sx={{ color: colors.text.focus, lineHeight: 1.35 }}
                display="block"
              >
                {item.reason}
              </MDTypography>
            )}
          </Card>
        ))}
      </MDBox>
    </MDBox>
  );
}

RecommendationsRail.defaultProps = {
  topK: 4,
};

RecommendationsRail.propTypes = {
  resourceId: PropTypes.string.isRequired,
  topK: PropTypes.number,
  onSelectResource: PropTypes.func.isRequired,
};

export default RecommendationsRail;
