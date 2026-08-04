import PropTypes from "prop-types";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";

import { CEFR_COLORS } from "assets/theme/base/cefr";

function CefrBadge({ level }) {
  const palette = CEFR_COLORS[level] || CEFR_COLORS.A1;

  return (
    <MDBox
      display="inline-flex"
      alignItems="center"
      justifyContent="center"
      px={1.25}
      py={0.35}
      borderRadius="md"
      sx={{
        backgroundColor: palette.bg,
        border: `1px solid ${palette.border}`,
      }}
    >
      <MDTypography
        variant="caption"
        fontWeight="bold"
        sx={{ color: palette.text, letterSpacing: "0.02em", lineHeight: 1.2 }}
      >
        {level}
      </MDTypography>
    </MDBox>
  );
}

CefrBadge.propTypes = {
  level: PropTypes.oneOf(["A1", "A2", "B1", "B2", "C1", "C2"]).isRequired,
};

export default CefrBadge;
