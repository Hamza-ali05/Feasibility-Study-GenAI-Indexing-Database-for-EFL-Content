
import PropTypes from "prop-types";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";

import colors from "assets/theme/base/colors";

const VARIANT_LABEL = {
  skill: "skill",
  topic: "topic",
  source: "source",
};

function TagBadge({ text, variant }) {
  const { grey, text: textColors } = colors;

  return (
    <MDBox
      display="inline-flex"
      alignItems="center"
      px={1.1}
      py={0.3}
      borderRadius="md"
      sx={{
        backgroundColor: grey[100],
        border: `1px solid ${grey[300]}`,
      }}
      title={variant ? VARIANT_LABEL[variant] : undefined}
    >
      <MDTypography
        variant="caption"
        fontWeight="regular"
        sx={{ color: textColors.focus, lineHeight: 1.2 }}
      >
        {text}
      </MDTypography>
    </MDBox>
  );
}

TagBadge.defaultProps = {
  variant: "topic",
};

TagBadge.propTypes = {
  text: PropTypes.string.isRequired,
  variant: PropTypes.oneOf(["skill", "topic", "source"]),
};

export default TagBadge;
