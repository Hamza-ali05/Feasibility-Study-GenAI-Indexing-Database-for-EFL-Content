import PropTypes from "prop-types";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";

import colors from "assets/theme/base/colors";

import StageStatusPill from "./StageStatusPill";

export const PIPELINE_STAGE_NAMES = [
  "Discover",
  "Load",
  "Integrate",
  "EDA",
  "Clean",
  "Split",
  "Preprocess",
  "Balance",
  "Train",
  "Evaluate",
  "Explain Global",
  "Explain Local",
  "Explain Quality",
  "Predict",
];

function statusForStage(stages, name) {
  const found = (stages || []).find((s) => s.name === name);
  return found?.status || "PENDING";
}

function PipelineProgressBar({ stages }) {
  return (
    <MDBox
      display="flex"
      alignItems="flex-start"
      sx={{
        overflowX: "auto",
        pb: 1,
        gap: 0,
      }}
    >
      {PIPELINE_STAGE_NAMES.map((name, index) => {
        const status = statusForStage(stages, name);
        const isLast = index === PIPELINE_STAGE_NAMES.length - 1;

        return (
          <MDBox key={name} display="flex" alignItems="flex-start" flexShrink={0}>
            <MDBox
              display="flex"
              flexDirection="column"
              alignItems="center"
              minWidth="5.5rem"
              px={0.5}
            >
              <StageStatusPill status={status} />
              <MDTypography
                variant="caption"
                mt={0.75}
                textAlign="center"
                sx={{ color: colors.text.secondary, maxWidth: "5.5rem", lineHeight: 1.2 }}
              >
                {name}
              </MDTypography>
            </MDBox>
            {!isLast && (
              <MDBox
                alignSelf="center"
                mx={0.25}
                mt={-2.5}
                sx={{
                  width: "1.25rem",
                  height: "2px",
                  backgroundColor: colors.grey[300],
                  flexShrink: 0,
                }}
              />
            )}
          </MDBox>
        );
      })}
    </MDBox>
  );
}

PipelineProgressBar.propTypes = {
  stages: PropTypes.arrayOf(
    PropTypes.shape({
      name: PropTypes.string.isRequired,
      status: PropTypes.oneOf(["PENDING", "RUNNING", "COMPLETE", "FAILED"]).isRequired,
    })
  ).isRequired,
};

export default PipelineProgressBar;
