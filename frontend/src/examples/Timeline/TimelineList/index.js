/**
=========================================================
* Material Dashboard 2 React - v2.2.0
=========================================================

* Product Page: https://www.creative-tim.com/product/material-dashboard-react
* Copyright 2023 Creative Tim (https://www.creative-tim.com)

Coded by www.creative-tim.com

 =========================================================

* The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
*/

import PropTypes from "prop-types";

import Card from "@mui/material/Card";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";

import { useMaterialUIController } from "context";

import { TimelineProvider } from "examples/Timeline/context";

function TimelineList({ title, dark, children }) {
  const [controller] = useMaterialUIController();
  const { darkMode } = controller;

  return (
    <TimelineProvider value={dark}>
      <Card>
        <MDBox
          bgColor={dark ? "dark" : "white"}
          variant="gradient"
          borderRadius="xl"
          sx={{ background: ({ palette: { background } }) => darkMode && background.card }}
        >
          <MDBox pt={3} px={3}>
            <MDTypography variant="h6" fontWeight="medium" color={dark ? "white" : "dark"}>
              {title}
            </MDTypography>
          </MDBox>
          <MDBox p={2}>{children}</MDBox>
        </MDBox>
      </Card>
    </TimelineProvider>
  );
}

TimelineList.defaultProps = {
  dark: false,
};

TimelineList.propTypes = {
  title: PropTypes.string.isRequired,
  dark: PropTypes.bool,
  children: PropTypes.node.isRequired,
};

export default TimelineList;
