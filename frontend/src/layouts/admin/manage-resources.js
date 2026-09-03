import { useCallback, useEffect, useState } from "react";
import PropTypes from "prop-types";

import Card from "@mui/material/Card";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import FormControl from "@mui/material/FormControl";
import Grid from "@mui/material/Grid";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Skeleton from "@mui/material/Skeleton";
import Icon from "@mui/material/Icon";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableContainer from "@mui/material/TableContainer";
import TableRow from "@mui/material/TableRow";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDButton from "components/MDButton";
import MDAlert from "components/MDAlert";
import MDPagination from "components/MDPagination";

import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";
import DataTableHeadCell from "examples/Tables/DataTable/DataTableHeadCell";
import DataTableBodyCell from "examples/Tables/DataTable/DataTableBodyCell";

import { CefrBadge, TagBadge } from "components/EflShared";
import DocumentPreviewModal from "components/EflShared/DocumentPreviewModal";

import {
  getResources,
  getSearchFacets,
  deleteResource,
  patchResourceLabels,
} from "services/endpoints";
import colors from "assets/theme/base/colors";
import { SKILL_TYPES, TOPIC_DOMAINS } from "assets/theme/base/eflLabels";

const PAGE_SIZE = 20;
const MANUAL_LABEL_MS = 10 * 60 * 1000;

const CEFR_OPTIONS = [
  { value: "A1", label: "A1 — Beginner" },
  { value: "A2", label: "A2 — Elementary" },
  { value: "B1", label: "B1 — Intermediate" },
  { value: "B2", label: "B2 — Upper intermediate" },
  { value: "C1", label: "C1 — Advanced" },
  { value: "C2", label: "C2 — Proficiency" },
];

const SKILL_OPTIONS = SKILL_TYPES.map((value) => ({ value, label: value }));
const TOPIC_OPTIONS = TOPIC_DOMAINS.map((value) => ({
  value,
  label: value === "Daily Life" ? "Daily life" : value,
}));

const selectMenuProps = {
  PaperProps: {
    sx: {
      minWidth: 280,
      maxHeight: 320,
      overflowY: "auto",
    },
  },
  anchorOrigin: { vertical: "bottom", horizontal: "left" },
  transformOrigin: { vertical: "top", horizontal: "left" },
};

const selectSx = {
  minWidth: 260,
  "& .MuiSelect-select": {
    minHeight: "2.75rem",
    display: "flex",
    alignItems: "center",
    py: 1.25,
    px: 2,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
};

function humanizeFacetValue(raw) {
  const text = String(raw || "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!text) return "";
  return text
    .split(" ")
    .map((word) => {
      if (/^[A-Z]\d$/i.test(word)) return word.toUpperCase();
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join(" ");
}

/** Always show canonical taxonomy; merge live facet counts when available. */
function buildFilterOptions(canonical, facetMap) {
  const counts = facetMap && typeof facetMap === "object" ? facetMap : {};
  const seen = new Set();
  const options = canonical.map((opt) => {
    seen.add(opt.value);
    return {
      value: opt.value,
      label: opt.label,
      count: Number(counts[opt.value]) || 0,
    };
  });

  Object.entries(counts).forEach(([value, count]) => {
    if (!value || seen.has(value)) return;
    options.push({
      value,
      label: humanizeFacetValue(value),
      count: Number(count) || 0,
    });
  });

  return options;
}

function isLabelEditable(item, nowMs) {
  if (!item?.created_at) return false;
  const then = Date.parse(item.created_at);
  if (Number.isNaN(then)) return false;
  return nowMs - then <= MANUAL_LABEL_MS;
}

function EditLabelsDialog({ open, item, onClose, onSaved }) {
  const [skill, setSkill] = useState("");
  const [topic, setTopic] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (open && item) {
      setSkill(item.skill_type || "");
      setTopic(item.topic_domain || "");
      setError(null);
    }
  }, [open, item]);

  const save = async () => {
    if (!item) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await patchResourceLabels(item.resource_id, {
        skill_type: skill || undefined,
        topic_domain: topic || undefined,
      });
      onSaved(updated);
      onClose();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Failed to save labels";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={() => !saving && onClose()} fullWidth maxWidth="sm">
      <DialogTitle>Edit skill / topic</DialogTitle>
      <DialogContent>
        <DialogContentText sx={{ mb: 2 }}>
          Analyzer fallback fields only — editable within 10 minutes of <code>created_at</code>.
        </DialogContentText>
        {error && (
          <MDBox mb={2}>
            <MDAlert color="error">{error}</MDAlert>
          </MDBox>
        )}
        <FormControl fullWidth size="small" sx={{ mb: 2 }}>
          <InputLabel id="admin-edit-skill">Skill type</InputLabel>
          <Select
            labelId="admin-edit-skill"
            label="Skill type"
            value={skill}
            onChange={(e) => setSkill(e.target.value)}
          >
            <MenuItem value="">
              <em>None</em>
            </MenuItem>
            {SKILL_TYPES.map((s) => (
              <MenuItem key={s} value={s}>
                {s}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl fullWidth size="small">
          <InputLabel id="admin-edit-topic">Topic domain</InputLabel>
          <Select
            labelId="admin-edit-topic"
            label="Topic domain"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
          >
            <MenuItem value="">
              <em>None</em>
            </MenuItem>
            {TOPIC_DOMAINS.map((t) => (
              <MenuItem key={t} value={t}>
                {t}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </DialogContent>
      <DialogActions>
        <MDButton
          variant="outlined"
          color="secondary"
          size="small"
          disabled={saving}
          onClick={onClose}
        >
          Cancel
        </MDButton>
        <MDButton
          variant="gradient"
          color="primary"
          size="small"
          disabled={saving || (!skill && !topic)}
          onClick={save}
        >
          {saving ? "Saving…" : "Save"}
        </MDButton>
      </DialogActions>
    </Dialog>
  );
}

EditLabelsDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  item: PropTypes.object,
  onClose: PropTypes.func.isRequired,
  onSaved: PropTypes.func.isRequired,
};

function ManageResources() {
  const [cefrLevel, setCefrLevel] = useState("");
  const [skillType, setSkillType] = useState("");
  const [topicDomain, setTopicDomain] = useState("");
  const [facets, setFacets] = useState({
    cefr_level: {},
    skill_type: {},
    topic_domain: {},
  });

  const [page, setPage] = useState(1);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [previewId, setPreviewId] = useState(null);
  const [nowMs, setNowMs] = useState(() => Date.now());

  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);
  const [editTarget, setEditTarget] = useState(null);

  const filtersActive = Boolean(cefrLevel || skillType || topicDomain);
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE) || 1);

  useEffect(() => {
    const tick = setInterval(() => setNowMs(Date.now()), 15000);
    return () => clearInterval(tick);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await getSearchFacets();
        if (!cancelled && data) {
          setFacets({
            cefr_level: data.cefr_level || {},
            skill_type: data.skill_type || {},
            topic_domain: data.topic_domain || {},
          });
        }
      } catch {}
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const fetchPage = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = { page, page_size: PAGE_SIZE };
      if (cefrLevel) params.cefr_level = cefrLevel;
      if (skillType) params.skill_type = skillType;
      if (topicDomain) params.topic_domain = topicDomain;

      const data = await getResources(params);
      setItems(Array.isArray(data?.items) ? data.items : []);
      setTotal(Number(data?.total) || 0);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Failed to load resources";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, cefrLevel, skillType, topicDomain]);

  useEffect(() => {
    fetchPage();
  }, [fetchPage]);

  const clearFilters = () => {
    setCefrLevel("");
    setSkillType("");
    setTopicDomain("");
    setPage(1);
  };

  const onFilterChange = (setter) => (event) => {
    setter(event.target.value);
    setPage(1);
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteResource(deleteTarget.resource_id);
      setDeleteTarget(null);
      await fetchPage();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Delete failed";
      setDeleteError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setDeleting(false);
    }
  };

  const cefrOpts = buildFilterOptions(CEFR_OPTIONS, facets.cefr_level);
  const skillOpts = buildFilterOptions(SKILL_OPTIONS, facets.skill_type);
  const topicOpts = buildFilterOptions(TOPIC_OPTIONS, facets.topic_domain);

  const renderPageButtons = () => {
    const buttons = [];
    const windowSize = 5;
    let start = Math.max(1, page - Math.floor(windowSize / 2));
    let end = Math.min(totalPages, start + windowSize - 1);
    start = Math.max(1, end - windowSize + 1);
    for (let p = start; p <= end; p += 1) {
      buttons.push(
        <MDPagination item key={p} active={p === page} onClick={() => setPage(p)}>
          {p}
        </MDPagination>
      );
    }
    return buttons;
  };

  return (
    <DashboardLayout>
      <DashboardNavbar />
      <MDBox py={3}>
        <Card sx={{ p: 2, mb: 3 }}>
          <Grid container spacing={2} alignItems="flex-end">
            <Grid item xs={12} sm={6} md={4}>
              <MDTypography
                variant="caption"
                fontWeight="medium"
                color="text"
                display="block"
                mb={0.5}
              >
                CEFR level
              </MDTypography>
              <FormControl fullWidth size="small">
                <Select
                  displayEmpty
                  value={cefrLevel}
                  onChange={onFilterChange(setCefrLevel)}
                  renderValue={(selected) => {
                    if (!selected) return "Any level";
                    const match = cefrOpts.find((o) => o.value === selected);
                    return match?.label || selected;
                  }}
                  MenuProps={selectMenuProps}
                  sx={selectSx}
                >
                  <MenuItem value="">
                    <em>Any level</em>
                  </MenuItem>
                  {cefrOpts.map((o) => (
                    <MenuItem key={o.value} value={o.value}>
                      {o.label}
                      {o.count > 0 ? ` (${o.count})` : ""}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <MDTypography
                variant="caption"
                fontWeight="medium"
                color="text"
                display="block"
                mb={0.5}
              >
                Skill type
              </MDTypography>
              <FormControl fullWidth size="small">
                <Select
                  displayEmpty
                  value={skillType}
                  onChange={onFilterChange(setSkillType)}
                  renderValue={(selected) => {
                    if (!selected) return "Any skill";
                    const match = skillOpts.find((o) => o.value === selected);
                    return match?.label || selected;
                  }}
                  MenuProps={selectMenuProps}
                  sx={selectSx}
                >
                  <MenuItem value="">
                    <em>Any skill</em>
                  </MenuItem>
                  {skillOpts.map((o) => (
                    <MenuItem key={o.value} value={o.value}>
                      {o.label}
                      {o.count > 0 ? ` (${o.count})` : ""}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <MDTypography
                variant="caption"
                fontWeight="medium"
                color="text"
                display="block"
                mb={0.5}
              >
                Topic domain
              </MDTypography>
              <FormControl fullWidth size="small">
                <Select
                  displayEmpty
                  value={topicDomain}
                  onChange={onFilterChange(setTopicDomain)}
                  renderValue={(selected) => {
                    if (!selected) return "Any topic";
                    const match = topicOpts.find((o) => o.value === selected);
                    return match?.label || selected;
                  }}
                  MenuProps={selectMenuProps}
                  sx={selectSx}
                >
                  <MenuItem value="">
                    <em>Any topic</em>
                  </MenuItem>
                  {topicOpts.map((o) => (
                    <MenuItem key={o.value} value={o.value}>
                      {o.label}
                      {o.count > 0 ? ` (${o.count})` : ""}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            {filtersActive && (
              <Grid item xs={12} sm="auto">
                <Chip
                  label="Clear filters"
                  onDelete={clearFilters}
                  onClick={clearFilters}
                  size="small"
                  variant="outlined"
                  sx={{ borderColor: colors.grey[300], mb: 0.25 }}
                />
              </Grid>
            )}
          </Grid>
        </Card>

        {error && (
          <MDBox mb={2}>
            <MDAlert color="error">{error}</MDAlert>
          </MDBox>
        )}

        <Card>
          <MDBox p={2}>
            <MDTypography variant="h6">
              Resources
              {!loading && (
                <MDTypography component="span" variant="button" color="text" ml={1}>
                  ({total} total)
                </MDTypography>
              )}
            </MDTypography>
          </MDBox>

          {loading ? (
            <MDBox px={2} pb={2}>
              {[0, 1, 2, 3, 4].map((i) => (
                <Skeleton key={i} height={40} sx={{ mb: 1 }} />
              ))}
            </MDBox>
          ) : items.length === 0 ? (
            <MDBox px={2} pb={3}>
              <MDTypography variant="button" color="text">
                No resources match these filters.
              </MDTypography>
            </MDBox>
          ) : (
            <TableContainer sx={{ boxShadow: "none" }}>
              <Table>
                <MDBox component="thead">
                  <TableRow>
                    <DataTableHeadCell width="26%" sorted={false}>
                      Title
                    </DataTableHeadCell>
                    <DataTableHeadCell align="center" width="8%" sorted={false}>
                      CEFR
                    </DataTableHeadCell>
                    <DataTableHeadCell align="center" width="12%" sorted={false}>
                      Skill
                    </DataTableHeadCell>
                    <DataTableHeadCell align="center" width="12%" sorted={false}>
                      Topic
                    </DataTableHeadCell>
                    <DataTableHeadCell width="12%" sorted={false}>
                      Source
                    </DataTableHeadCell>
                    <DataTableHeadCell align="right" width="30%" sorted={false}>
                      Actions
                    </DataTableHeadCell>
                  </TableRow>
                </MDBox>
                <TableBody>
                  {items.map((item) => {
                    const cefrOk =
                      item.cefr_level &&
                      ["A1", "A2", "B1", "B2", "C1", "C2"].includes(item.cefr_level);
                    const editable = isLabelEditable(item, nowMs);
                    return (
                      <TableRow key={item.resource_id}>
                        <DataTableBodyCell>
                          <MDTypography variant="button" fontWeight="medium">
                            {item.title}
                          </MDTypography>
                        </DataTableBodyCell>
                        <DataTableBodyCell align="center">
                          {cefrOk ? <CefrBadge level={item.cefr_level} /> : "—"}
                        </DataTableBodyCell>
                        <DataTableBodyCell align="center">
                          {item.skill_type ? (
                            <TagBadge text={item.skill_type} variant="skill" />
                          ) : (
                            "—"
                          )}
                        </DataTableBodyCell>
                        <DataTableBodyCell align="center">
                          {item.topic_domain ? (
                            <TagBadge text={item.topic_domain} variant="topic" />
                          ) : (
                            "—"
                          )}
                        </DataTableBodyCell>
                        <DataTableBodyCell>
                          <MDTypography variant="caption" color="text">
                            {item.source_name || "—"}
                          </MDTypography>
                        </DataTableBodyCell>
                        <DataTableBodyCell align="right">
                          <MDBox
                            display="inline-flex"
                            flexWrap="wrap"
                            gap={0.75}
                            justifyContent="flex-end"
                          >
                            <MDButton
                              variant="outlined"
                              color="secondary"
                              size="small"
                              onClick={() => setPreviewId(item.resource_id)}
                            >
                              Preview
                            </MDButton>
                            {editable ? (
                              <MDButton
                                variant="outlined"
                                color="info"
                                size="small"
                                onClick={() => setEditTarget(item)}
                              >
                                Edit
                              </MDButton>
                            ) : (
                              <MDTypography
                                variant="caption"
                                color="text"
                                sx={{ alignSelf: "center", px: 0.5 }}
                              >
                                labels read-only
                              </MDTypography>
                            )}
                            <MDButton
                              variant="gradient"
                              color="error"
                              size="small"
                              onClick={() => {
                                setDeleteError(null);
                                setDeleteTarget(item);
                              }}
                            >
                              Delete
                            </MDButton>
                          </MDBox>
                        </DataTableBodyCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}

          {!loading && total > 0 && (
            <MDBox
              display="flex"
              justifyContent="space-between"
              alignItems="center"
              flexWrap="wrap"
              gap={1}
              p={2}
              sx={{ borderTop: `1px solid ${colors.grey[300]}` }}
            >
              <MDTypography variant="caption" color="text">
                Page {page} of {totalPages}
              </MDTypography>
              <MDPagination variant="gradient" color="primary">
                <MDPagination
                  item
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                >
                  <Icon>chevron_left</Icon>
                </MDPagination>
                {renderPageButtons()}
                <MDPagination
                  item
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                >
                  <Icon>chevron_right</Icon>
                </MDPagination>
              </MDPagination>
            </MDBox>
          )}
        </Card>
      </MDBox>

      <DocumentPreviewModal
        open={Boolean(previewId)}
        resourceId={previewId}
        onClose={() => setPreviewId(null)}
      />

      <EditLabelsDialog
        open={Boolean(editTarget)}
        item={editTarget}
        onClose={() => setEditTarget(null)}
        onSaved={(updated) => {
          setItems((prev) =>
            prev.map((row) =>
              row.resource_id === updated.resource_id
                ? {
                    ...row,
                    skill_type: updated.skill_type,
                    topic_domain: updated.topic_domain,
                  }
                : row
            )
          );
        }}
      />

      <Dialog open={Boolean(deleteTarget)} onClose={() => !deleting && setDeleteTarget(null)}>
        <DialogTitle>Delete resource?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Remove <strong>{deleteTarget?.title || deleteTarget?.resource_id}</strong> from metadata
            and tombstone it in FAISS. This cannot be undone from the UI.
          </DialogContentText>
          {deleteError && (
            <MDBox mt={2}>
              <MDAlert color="error">{deleteError}</MDAlert>
            </MDBox>
          )}
        </DialogContent>
        <DialogActions>
          <MDButton
            variant="outlined"
            color="secondary"
            size="small"
            disabled={deleting}
            onClick={() => setDeleteTarget(null)}
          >
            Cancel
          </MDButton>
          <MDButton
            variant="gradient"
            color="error"
            size="small"
            disabled={deleting}
            onClick={confirmDelete}
          >
            {deleting ? (
              <MDBox display="inline-flex" alignItems="center" gap={1}>
                <CircularProgress size={14} color="inherit" />
                Deleting…
              </MDBox>
            ) : (
              "Delete"
            )}
          </MDButton>
        </DialogActions>
      </Dialog>

      <Footer />
    </DashboardLayout>
  );
}

export default ManageResources;
