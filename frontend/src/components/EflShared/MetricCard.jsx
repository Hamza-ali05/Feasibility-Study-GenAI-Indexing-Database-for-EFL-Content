import PropTypes from "prop-types";

import Card from "@mui/material/Card";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";

function MetricCard({ label, value, delta, positive }) {
  const showDelta = delta !== undefined && delta !== null && delta !== "";

  return (
    <Card sx={{ height: "100%" }}>
      <MDBox p={2} lineHeight={1.25}>
        <MDTypography variant="button" fontWeight="light" color="text">
          {label}
        </MDTypography>
        <MDTypography variant="h4" fontWeight="bold" mt={0.5}>
          {value}
        </MDTypography>
        {showDelta && (
          <MDBox mt={1}>
            <MDTypography
              variant="caption"
              fontWeight="bold"
              color={positive ? "success" : "error"}
            >
              {delta}
            </MDTypography>
          </MDBox>
        )}
      </MDBox>
    </Card>
  );
}

MetricCard.defaultProps = {
  delta: undefined,
  positive: true,
};

MetricCard.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.string.isRequired,
  delta: PropTypes.string,
  positive: PropTypes.bool,
};

export default MetricCard;
