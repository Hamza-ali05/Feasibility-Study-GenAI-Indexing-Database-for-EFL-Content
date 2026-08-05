import { Fragment, useCallback, useEffect, useState } from "react";

import Card from "@mui/material/Card";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Collapse from "@mui/material/Collapse";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import FormControl from "@mui/material/FormControl";
import IconButton from "@mui/material/IconButton";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowUpIcon from "@mui/icons-material/KeyboardArrowUp";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDButton from "components/MDButton";
import MDAlert from "components/MDAlert";
import MDInput from "components/MDInput";

import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";
import DataTableHeadCell from "examples/Tables/DataTable/DataTableHeadCell";
import DataTableBodyCell from "examples/Tables/DataTable/DataTableBodyCell";

import {
  createPractitionerParticipant,
  getPractitionerParticipants,
  updatePractitionerStatus,
  withdrawPractitioner,
} from "services/endpoints";

const STATUSES = ["Recruited", "Consented", "Interviewed", "Transcribed", "Coded", "Withdrawn"];

const CONTEXTS = ["Primary", "Secondary", "Adult", "Academic English"];

const STATUS_COLOR = {
  Recruited: "default",
  Consented: "info",
  Interviewed: "primary",
  Transcribed: "secondary",
  Coded: "success",
  Withdrawn: "error",
};

const EMPTY_FORM = {
  pseudonym: "",
  teaching_context: "Adult",
  years_experience: 5,
  institution_type: "",
  recruited_via: "Professional Network",
  consent_given: false,
  status: "Recruited",
};

function statusChip(status) {
  return (
    <Chip
      size="small"
      label={status || "—"}
      color={STATUS_COLOR[status] || "default"}
      variant={status === "Withdrawn" ? "outlined" : "filled"}
    />
  );
}

function PractitionerManage() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState(null);
  const [expanded, setExpanded] = useState({});
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [statusTarget, setStatusTarget] = useState(null);
  const [nextStatus, setNextStatus] = useState("Consented");
  const [withdrawTarget, setWithdrawTarget] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getPractitionerParticipants();
      setRows(Array.isArray(data) ? data : []);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Failed to load";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const toggleExpand = (id) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const submitAdd = async () => {
    setSaving(true);
    setError(null);
    setMsg(null);
    try {
      await createPractitionerParticipant({
        ...form,
        years_experience: Number(form.years_experience) || 0,
        consent_date: form.consent_given ? new Date().toISOString().slice(0, 10) : null,
      });
      setAddOpen(false);
      setForm(EMPTY_FORM);
      setMsg("Participant added.");
      await load();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Create failed";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setSaving(false);
    }
  };

  const applyStatus = async () => {
    if (!statusTarget) return;
    setBusyId(statusTarget.participant_id);
    setError(null);
    setMsg(null);
    try {
      await updatePractitionerStatus(statusTarget.participant_id, nextStatus);
      setStatusTarget(null);
      setMsg(`Status updated to ${nextStatus}.`);
      await load();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Update failed";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setBusyId(null);
    }
  };

  const confirmWithdraw = async () => {
    if (!withdrawTarget) return;
    setBusyId(withdrawTarget.participant_id);
    setError(null);
    setMsg(null);
    try {
      await withdrawPractitioner(withdrawTarget.participant_id);
      setWithdrawTarget(null);
      setMsg(`${withdrawTarget.pseudonym} withdrawn; artefacts purged.`);
      await load();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Withdraw failed";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <DashboardLayout>
      <DashboardNavbar hideBreadcrumbs />
      <MDBox py={3}>
        <MDBox
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          mb={2}
          flexWrap="wrap"
          gap={1}
        >
          <MDTypography variant="h4" fontWeight="bold">
            Manage Participants
          </MDTypography>
          <MDButton
            variant="gradient"
            color="primary"
            size="small"
            onClick={() => {
              setForm(EMPTY_FORM);
              setAddOpen(true);
            }}
          >
            Add Participant
          </MDButton>
        </MDBox>

        {error && (
          <MDBox mb={2}>
            <MDAlert color="error">{error}</MDAlert>
          </MDBox>
        )}
        {msg && (
          <MDBox mb={2}>
            <MDAlert color="success">{msg}</MDAlert>
          </MDBox>
        )}

        <Card>
          {loading ? (
            <MDBox display="flex" justifyContent="center" py={6}>
              <CircularProgress color="info" />
            </MDBox>
          ) : (
            <TableContainer sx={{ boxShadow: "none" }}>
              <Table>
                <MDBox component="thead">
                  <TableRow>
                    <DataTableHeadCell width="4%"> </DataTableHeadCell>
                    <DataTableHeadCell>Pseudonym</DataTableHeadCell>
                    <DataTableHeadCell>Context</DataTableHeadCell>
                    <DataTableHeadCell>Years</DataTableHeadCell>
                    <DataTableHeadCell>Institution</DataTableHeadCell>
                    <DataTableHeadCell>Status</DataTableHeadCell>
                    <DataTableHeadCell align="right">Actions</DataTableHeadCell>
                  </TableRow>
                </MDBox>
                <TableBody>
                  {rows.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={7}>
                        <MDTypography variant="button" color="text">
                          No participants yet. Use Add Participant to recruit (pseudonyms only).
                        </MDTypography>
                      </TableCell>
                    </TableRow>
                  )}
                  {rows.map((row) => {
                    const open = Boolean(expanded[row.participant_id]);
                    const withdrawn = row.status === "Withdrawn";
                    return (
                      <Fragment key={row.participant_id}>
                        <TableRow hover>
                          <DataTableBodyCell>
                            <IconButton
                              size="small"
                              onClick={() => toggleExpand(row.participant_id)}
                              aria-label="expand"
                            >
                              {open ? (
                                <KeyboardArrowUpIcon fontSize="small" />
                              ) : (
                                <KeyboardArrowDownIcon fontSize="small" />
                              )}
                            </IconButton>
                          </DataTableBodyCell>
                          <DataTableBodyCell>
                            <MDTypography variant="button" fontWeight="medium">
                              {row.pseudonym}
                            </MDTypography>
                          </DataTableBodyCell>
                          <DataTableBodyCell>{row.teaching_context}</DataTableBodyCell>
                          <DataTableBodyCell>{row.years_experience}</DataTableBodyCell>
                          <DataTableBodyCell>{row.institution_type}</DataTableBodyCell>
                          <DataTableBodyCell>{statusChip(row.status)}</DataTableBodyCell>
                          <DataTableBodyCell align="right">
                            <MDBox display="inline-flex" gap={0.5}>
                              <MDButton
                                variant="outlined"
                                color="info"
                                size="small"
                                disabled={withdrawn || busyId === row.participant_id}
                                onClick={() => {
                                  setStatusTarget(row);
                                  setNextStatus(
                                    row.status === "Withdrawn" ? "Recruited" : row.status
                                  );
                                }}
                              >
                                Update Status
                              </MDButton>
                              <MDButton
                                variant="outlined"
                                color="error"
                                size="small"
                                disabled={withdrawn || busyId === row.participant_id}
                                onClick={() => setWithdrawTarget(row)}
                              >
                                Withdraw
                              </MDButton>
                            </MDBox>
                          </DataTableBodyCell>
                        </TableRow>
                        <TableRow>
                          <TableCell
                            colSpan={7}
                            sx={{ py: 0, borderBottom: open ? undefined : "none" }}
                          >
                            <Collapse in={open} timeout="auto" unmountOnExit>
                              <MDBox p={2} bgcolor="grey.100" borderRadius="md">
                                <MDTypography variant="button" fontWeight="bold" mb={1}>
                                  Interview record
                                </MDTypography>
                                {row.interview ? (
                                  <MDTypography
                                    variant="caption"
                                    color="text"
                                    component="pre"
                                    sx={{ whiteSpace: "pre-wrap", mb: 2 }}
                                  >
                                    {JSON.stringify(row.interview, null, 2)}
                                  </MDTypography>
                                ) : (
                                  <MDTypography
                                    variant="caption"
                                    color="text"
                                    display="block"
                                    mb={2}
                                  >
                                    No interview linked.
                                  </MDTypography>
                                )}
                                <MDTypography variant="button" fontWeight="bold" mb={1}>
                                  Questionnaire responses
                                </MDTypography>
                                {(row.questionnaire_responses || []).length === 0 ? (
                                  <MDTypography variant="caption" color="text">
                                    No responses stored.
                                  </MDTypography>
                                ) : (
                                  <MDTypography
                                    variant="caption"
                                    color="text"
                                    component="pre"
                                    sx={{ whiteSpace: "pre-wrap" }}
                                  >
                                    {JSON.stringify(row.questionnaire_responses, null, 2)}
                                  </MDTypography>
                                )}
                              </MDBox>
                            </Collapse>
                          </TableCell>
                        </TableRow>
                      </Fragment>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Card>
      </MDBox>

      {/* Add participant */}
      <Dialog open={addOpen} onClose={() => !saving && setAddOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Add Participant</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 2 }}>
            Use a pseudonym only (e.g. P1). Never enter real names.
          </DialogContentText>
          <MDBox display="flex" flexDirection="column" gap={2} mt={1}>
            <MDInput
              label="Pseudonym"
              fullWidth
              value={form.pseudonym}
              onChange={(e) => setForm({ ...form, pseudonym: e.target.value })}
            />
            <FormControl fullWidth size="small">
              <InputLabel id="ctx-label">Teaching context</InputLabel>
              <Select
                labelId="ctx-label"
                label="Teaching context"
                value={form.teaching_context}
                onChange={(e) => setForm({ ...form, teaching_context: e.target.value })}
              >
                {CONTEXTS.map((c) => (
                  <MenuItem key={c} value={c}>
                    {c}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="Years experience"
              type="number"
              size="small"
              fullWidth
              value={form.years_experience}
              onChange={(e) => setForm({ ...form, years_experience: e.target.value })}
              inputProps={{ min: 0 }}
            />
            <MDInput
              label="Institution type"
              fullWidth
              value={form.institution_type}
              onChange={(e) => setForm({ ...form, institution_type: e.target.value })}
            />
            <MDInput
              label="Recruited via"
              fullWidth
              value={form.recruited_via}
              onChange={(e) => setForm({ ...form, recruited_via: e.target.value })}
            />
            <FormControl fullWidth size="small">
              <InputLabel id="status-label">Initial status</InputLabel>
              <Select
                labelId="status-label"
                label="Initial status"
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value })}
              >
                {STATUSES.filter((s) => s !== "Withdrawn").map((s) => (
                  <MenuItem key={s} value={s}>
                    {s}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth size="small">
              <InputLabel id="consent-label">Consent given</InputLabel>
              <Select
                labelId="consent-label"
                label="Consent given"
                value={form.consent_given ? "yes" : "no"}
                onChange={(e) => setForm({ ...form, consent_given: e.target.value === "yes" })}
              >
                <MenuItem value="no">No</MenuItem>
                <MenuItem value="yes">Yes</MenuItem>
              </Select>
            </FormControl>
          </MDBox>
        </DialogContent>
        <DialogActions>
          <MDButton
            variant="outlined"
            color="secondary"
            disabled={saving}
            onClick={() => setAddOpen(false)}
          >
            Cancel
          </MDButton>
          <MDButton
            variant="gradient"
            color="primary"
            disabled={saving || !form.pseudonym.trim() || !form.institution_type.trim()}
            onClick={submitAdd}
          >
            {saving ? "Saving…" : "Create"}
          </MDButton>
        </DialogActions>
      </Dialog>

      {/* Update status */}
      <Dialog
        open={Boolean(statusTarget)}
        onClose={() => setStatusTarget(null)}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>Update status — {statusTarget?.pseudonym}</DialogTitle>
        <DialogContent>
          <FormControl fullWidth size="small" sx={{ mt: 1 }}>
            <InputLabel id="next-status">Status</InputLabel>
            <Select
              labelId="next-status"
              label="Status"
              value={nextStatus}
              onChange={(e) => setNextStatus(e.target.value)}
            >
              {STATUSES.filter((s) => s !== "Withdrawn").map((s) => (
                <MenuItem key={s} value={s}>
                  {s}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <MDButton variant="outlined" color="secondary" onClick={() => setStatusTarget(null)}>
            Cancel
          </MDButton>
          <MDButton variant="gradient" color="info" onClick={applyStatus}>
            Save
          </MDButton>
        </DialogActions>
      </Dialog>

      {/* Withdraw confirm */}
      <Dialog
        open={Boolean(withdrawTarget)}
        onClose={() => setWithdrawTarget(null)}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>Withdraw {withdrawTarget?.pseudonym}?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            This sets status to Withdrawn and deletes associated transcript and coded segments from
            the repository (CCCU retention / right to withdraw). Audio on the CCCU secure server
            must be purged separately.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <MDButton variant="outlined" color="secondary" onClick={() => setWithdrawTarget(null)}>
            Cancel
          </MDButton>
          <MDButton variant="gradient" color="error" onClick={confirmWithdraw}>
            Confirm withdraw
          </MDButton>
        </DialogActions>
      </Dialog>

      <Footer />
    </DashboardLayout>
  );
}

export default PractitionerManage;
