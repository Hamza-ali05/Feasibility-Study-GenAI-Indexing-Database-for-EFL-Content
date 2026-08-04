import PropTypes from "prop-types";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";

import colors from "assets/theme/base/colors";

function LiveIndicator({ connected }) {
  const dotColor = connected ? colors.success.main : colors.grey[500];
  const label = connected ? "Live" : "Reconnecting…";

  return (
    <MDBox display="inline-flex" alignItems="center" gap={0.75}>
      <MDBox
        width="0.55rem"
        height="0.55rem"
        borderRadius="50%"
        sx={{
          backgroundColor: dotColor,
          boxShadow: connected ? `0 0 0 3px ${colors.badgeColors.success.background}` : "none",
        }}
      />
      <MDTypography
        variant="caption"
        fontWeight="medium"
        sx={{ color: connected ? colors.success.main : colors.text.focus }}
      >
        {label}
      </MDTypography>
    </MDBox>
  );
}

LiveIndicator.propTypes = {
  connected: PropTypes.bool.isRequired,
};

export default LiveIndicator;
