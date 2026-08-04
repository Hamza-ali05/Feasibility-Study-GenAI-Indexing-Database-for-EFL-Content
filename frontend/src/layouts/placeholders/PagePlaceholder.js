import PropTypes from "prop-types";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";

function PagePlaceholder({ title }) {
  return (
    <DashboardLayout>
      <DashboardNavbar />
      <MDBox py={3} px={2}>
        <MDTypography variant="h5" fontWeight="medium">
          TODO{title ? `: ${title}` : ""}
        </MDTypography>
      </MDBox>
    </DashboardLayout>
  );
}

PagePlaceholder.defaultProps = {
  title: "",
};

PagePlaceholder.propTypes = {
  title: PropTypes.string,
};

export default PagePlaceholder;
