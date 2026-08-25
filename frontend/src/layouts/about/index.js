import Card from "@mui/material/Card";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";

import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";

function About() {
  return (
    <DashboardLayout>
      <DashboardNavbar />
      <MDBox py={3}>
        <MDTypography variant="h4" fontWeight="bold" mb={2}>
          About
        </MDTypography>

        <Card sx={{ p: 3, maxWidth: 720 }}>
          <MDTypography variant="body2" color="text" sx={{ lineHeight: 1.85 }} component="div">
            <p style={{ marginTop: 0 }}>
              EFL IndexDB is a research prototype that helps teachers and learners find English as a
              Foreign Language (EFL) materials more easily.
            </p>
            <p>
              It stores learning resources in a searchable index so you can look up content by
              meaning, not only by exact keywords.
            </p>
            <p>
              Results can be filtered by CEFR level, skill type, and topic, so you get materials
              that match the learner’s level and lesson focus.
            </p>
            <p>
              The app also supports asking questions about the corpus, reviewing similar resources,
              and checking how well different search methods perform.
            </p>
            <p style={{ marginBottom: 0 }}>
              This is an academic feasibility study built by Muhammad Yousaf (P18736) at Canterbury
              Christ Church University — a prototype for research, not a full production product.
            </p>
          </MDTypography>
        </Card>
      </MDBox>
      <Footer />
    </DashboardLayout>
  );
}

export default About;
