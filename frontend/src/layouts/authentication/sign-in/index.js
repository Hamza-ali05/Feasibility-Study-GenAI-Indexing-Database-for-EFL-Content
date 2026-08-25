import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import Card from "@mui/material/Card";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDInput from "components/MDInput";
import MDButton from "components/MDButton";
import MDAlert from "components/MDAlert";

import BasicLayout from "layouts/authentication/components/BasicLayout";
import { useAuth } from "context/AuthContext";

import bgImage from "assets/images/bg-sign-in-basic.jpeg";

function SignIn() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username.trim(), password);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Sign in failed";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <BasicLayout image={bgImage}>
      <Card>
        <MDBox
          variant="gradient"
          bgColor="primary"
          borderRadius="lg"
          coloredShadow="primary"
          mx={2}
          mt={-3}
          p={2}
          mb={1}
          textAlign="center"
        >
          <MDTypography variant="h4" fontWeight="medium" color="white" mt={1}>
            Admin Sign In
          </MDTypography>
          <MDTypography variant="caption" color="white" opacity={0.85}>
            EFL IndexDB control panel
          </MDTypography>
        </MDBox>
        <MDBox pt={4} pb={3} px={3}>
          {error && (
            <MDBox mb={2}>
              <MDAlert color="error">{error}</MDAlert>
            </MDBox>
          )}
          <MDBox component="form" role="form" onSubmit={handleSubmit}>
            <MDBox mb={3} mt={1}>
              <MDInput
                type="text"
                label="Username"
                fullWidth
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
                InputLabelProps={{ shrink: true }}
              />
            </MDBox>
            <MDBox mb={3}>
              <MDInput
                type="password"
                label="Password"
                fullWidth
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                InputLabelProps={{ shrink: true }}
              />
            </MDBox>
            <MDBox mt={2} mb={1}>
              <MDButton
                type="submit"
                variant="gradient"
                color="primary"
                fullWidth
                disabled={submitting || !username.trim() || !password}
              >
                {submitting ? "Signing in…" : "Sign In"}
              </MDButton>
            </MDBox>
          </MDBox>
        </MDBox>
      </Card>
    </BasicLayout>
  );
}

export default SignIn;
