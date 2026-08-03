
import PropTypes from "prop-types";

import CircularProgress from "@mui/material/CircularProgress";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";

import colors from "assets/theme/base/colors";

const STATUS_STYLES = {
  PENDING: {
    bg: colors.grey[200],
    border: colors.grey[300],
    text: colors.text.focus,
  },
  RUNNING: {
    bg: colors.badgeColors.warning.background,
    border: colors.warning.main,
    text: colors.warning.focus,
  },
  COMPLETE: {
    bg: colors.badgeColors.success.background,
    border: colors.success.main,
    text: colors.success.main,
  },
  FAILED: {
    bg: colors.badgeColors.error.background,
    border: colors.error.main,
    text: colors.error.main,
  },
};

function StageStatusPill({ status }) {
  const style = STATUS_STYLES[status] || STATUS_STYLES.PENDING;
  const isRunning = status === "RUNNING";

  return (
    <MDBox
      display="inline-flex"
      alignItems="center"
      gap={0.75}
      px={1.25}
      py={0.4}
      borderRadius="md"
      sx={{
        backgroundColor: style.bg,
        border: `1px solid ${style.border}`,
        whiteSpace: "nowrap",
      }}
    >
      {isRunning && <CircularProgress size={12} thickness={5} sx={{ color: style.text }} />}
      <MDTypography
        variant="caption"
        fontWeight="bold"
        sx={{ color: style.text, lineHeight: 1.2, letterSpacing: "0.04em" }}
      >
        {status}
      </MDTypography>
    </MDBox>
  );
}

StageStatusPill.propTypes = {
  status: PropTypes.oneOf(["PENDING", "RUNNING", "COMPLETE", "FAILED"]).isRequired,
};

export default StageStatusPill;
