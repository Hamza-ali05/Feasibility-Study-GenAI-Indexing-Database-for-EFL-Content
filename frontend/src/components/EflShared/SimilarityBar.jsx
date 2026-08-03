
import PropTypes from "prop-types";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";

import colors from "assets/theme/base/colors";

function hexToRgb(hex) {
  const h = hex.replace("#", "");
  const full =
    h.length === 3
      ? h
          .split("")
          .map((c) => c + c)
          .join("")
      : h;
  const n = parseInt(full, 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}

function lerpChannel(a, b, t) {
  return Math.round(a + (b - a) * t);
}

function interpolateHex(fromHex, toHex, t) {
  const clamped = Math.min(1, Math.max(0, t));
  const a = hexToRgb(fromHex);
  const b = hexToRgb(toHex);
  const r = lerpChannel(a.r, b.r, clamped);
  const g = lerpChannel(a.g, b.g, clamped);
  const bl = lerpChannel(a.b, b.b, clamped);
  return `rgb(${r}, ${g}, ${bl})`;
}

function SimilarityBar({ value }) {
  const clamped = Math.min(1, Math.max(0, Number(value) || 0));
  const pct = Math.round(clamped * 100);
  const border = colors.inputBorderColor || colors.grey[300];
  const accent = colors.primary.main;
  const fill = interpolateHex(border, accent, clamped);

  return (
    <MDBox display="flex" alignItems="center" width="100%" gap={1}>
      <MDBox
        flex={1}
        height="0.5rem"
        borderRadius="sm"
        sx={{ backgroundColor: colors.grey[200], overflow: "hidden" }}
      >
        <MDBox
          height="100%"
          borderRadius="sm"
          sx={{
            width: `${pct}%`,
            backgroundColor: fill,
            transition: "width 0.2s ease",
          }}
        />
      </MDBox>
      <MDTypography
        variant="caption"
        fontWeight="medium"
        sx={{ color: colors.text.secondary, minWidth: "2.5rem", textAlign: "right" }}
      >
        {pct}%
      </MDTypography>
    </MDBox>
  );
}

SimilarityBar.propTypes = {
  value: PropTypes.number.isRequired,
};

export default SimilarityBar;
