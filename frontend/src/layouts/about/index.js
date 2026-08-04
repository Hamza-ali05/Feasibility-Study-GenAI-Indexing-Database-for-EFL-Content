import Card from "@mui/material/Card";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDAlert from "components/MDAlert";

import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";

import colors from "assets/theme/base/colors";

const TECH_STACK = [
  {
    layer: "Embeddings",
    tech: "SBERT (Sentence-BERT)",
    role: "Semantic vectorisation of EFL learning resources",
  },
  {
    layer: "Vector index",
    tech: "FAISS (IndexFlatIP)",
    role: "Approximate nearest-neighbour retrieval over embedding space",
  },
  {
    layer: "API / pipeline",
    tech: "FastAPI (Python)",
    role: "REST API, ML pipeline stages, WebSocket live events",
  },
  {
    layer: "Frontend",
    tech: "EFL IndexDB",
    role: "Admin and end-user UI (MUI-based dashboard template)",
  },
];

function About() {
  return (
    <DashboardLayout>
      <DashboardNavbar />
      <MDBox py={3}>
        <MDTypography variant="h4" fontWeight="bold" mb={0.5}>
          Feasibility Study: GenAI Indexing Database for EFL Content
        </MDTypography>
        <MDTypography variant="button" color="text" mb={3} display="block">
          Academic prototype · Canterbury Christ Church University
        </MDTypography>

        <Card sx={{ p: 3, mb: 3 }}>
          <MDTypography variant="h6" mb={1.5}>
            Author
          </MDTypography>
          <MDTypography variant="body2" color="text" mb={0.5}>
            Muhammad Yousaf
          </MDTypography>
          <MDTypography variant="button" color="text" display="block">
            Student ID: P18736
          </MDTypography>
          <MDTypography variant="button" color="text" display="block">
            MSc Cybersecurity · Canterbury Christ Church University (CCCU)
          </MDTypography>

          <MDTypography variant="h6" mt={3} mb={1}>
            Supervisor
          </MDTypography>
          <MDTypography variant="body2" color="text">
            Victor Obarafor
          </MDTypography>
        </Card>

        <Card sx={{ p: 3, mb: 3 }}>
          <MDTypography variant="h6" mb={1.5}>
            Research question
          </MDTypography>
          <MDTypography variant="body2" color="text" sx={{ lineHeight: 1.7 }}>
            Can a generative-AI-assisted indexing database — combining sentence embeddings, vector
            search, CEFR-aware classification, and explainability — feasibly support discovery and
            organisation of English as a Foreign Language (EFL) learning resources at a quality and
            operational cost suitable for a small-scale academic prototype, and what design
            trade-offs emerge when SBERT/FAISS retrieval is compared with classical TF-IDF baselines
            under realistic pipeline and UI constraints?
          </MDTypography>
        </Card>

        <Card sx={{ p: 3, mb: 3, overflowX: "auto" }}>
          <MDTypography variant="h6" mb={1.5}>
            Tech stack
          </MDTypography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>
                  <MDTypography variant="caption" fontWeight="bold">
                    Layer
                  </MDTypography>
                </TableCell>
                <TableCell>
                  <MDTypography variant="caption" fontWeight="bold">
                    Technology
                  </MDTypography>
                </TableCell>
                <TableCell>
                  <MDTypography variant="caption" fontWeight="bold">
                    Role in this study
                  </MDTypography>
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {TECH_STACK.map((row) => (
                <TableRow
                  key={row.layer}
                  sx={{
                    "& td": { borderColor: colors.grey[300] },
                  }}
                >
                  <TableCell>
                    <MDTypography variant="button" fontWeight="medium">
                      {row.layer}
                    </MDTypography>
                  </TableCell>
                  <TableCell>
                    <MDTypography variant="button">{row.tech}</MDTypography>
                  </TableCell>
                  <TableCell>
                    <MDTypography variant="caption" color="text">
                      {row.role}
                    </MDTypography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>

        <MDAlert color="info">
          This application is a feasibility-study prototype built for an academic dissertation. It
          is not a production product: security, scale, and operational hardening are intentionally
          limited to what the study required.
        </MDAlert>
      </MDBox>
      <Footer />
    </DashboardLayout>
  );
}

export default About;
