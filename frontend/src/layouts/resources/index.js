
import { useCallback, useEffect, useState } from "react";

import Card from "@mui/material/Card";
import Chip from "@mui/material/Chip";
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

import { getResources, getSearchFacets } from "services/endpoints";
import colors from "assets/theme/base/colors";

const PAGE_SIZE = 20;

function facetOptions(facetMap) {
  if (!facetMap || typeof facetMap !== "object") return [];
  return Object.entries(facetMap)
    .map(([value, count]) => ({ value, count: Number(count) || 0 }))
    .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value));
}

function BrowseResources() {
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

  const filtersActive = Boolean(cefrLevel || skillType || topicDomain);
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE) || 1);

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
      } catch (err) {

      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const fetchPage = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {
        page,
        page_size: PAGE_SIZE,
      };
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

  const cefrOpts = facetOptions(facets.cefr_level);
  const skillOpts = facetOptions(facets.skill_type);
  const topicOpts = facetOptions(facets.topic_domain);

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
        <MDTypography variant="h4" fontWeight="bold" mb={0.5}>
          Browse Resources
        </MDTypography>
        <MDTypography variant="button" color="text" mb={3} display="block">
          Catalogue of indexed EFL resources
        </MDTypography>

        <Card sx={{ p: 2, mb: 3 }}>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} sm={4} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel id="browse-cefr">CEFR level</InputLabel>
                <Select
                  labelId="browse-cefr"
                  label="CEFR level"
                  value={cefrLevel}
                  onChange={onFilterChange(setCefrLevel)}
                >
                  <MenuItem value="">
                    <em>Any</em>
                  </MenuItem>
                  {cefrOpts.map((o) => (
                    <MenuItem key={o.value} value={o.value}>
                      {o.value} ({o.count})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={4} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel id="browse-skill">Skill type</InputLabel>
                <Select
                  labelId="browse-skill"
                  label="Skill type"
                  value={skillType}
                  onChange={onFilterChange(setSkillType)}
                >
                  <MenuItem value="">
                    <em>Any</em>
                  </MenuItem>
                  {skillOpts.map((o) => (
                    <MenuItem key={o.value} value={o.value}>
                      {o.value} ({o.count})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={4} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel id="browse-topic">Topic domain</InputLabel>
                <Select
                  labelId="browse-topic"
                  label="Topic domain"
                  value={topicDomain}
                  onChange={onFilterChange(setTopicDomain)}
                >
                  <MenuItem value="">
                    <em>Any</em>
                  </MenuItem>
                  {topicOpts.map((o) => (
                    <MenuItem key={o.value} value={o.value}>
                      {o.value} ({o.count})
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
                  sx={{ borderColor: colors.grey[300] }}
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
          <MDBox p={2} display="flex" justifyContent="space-between" alignItems="center">
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
                    <DataTableHeadCell width="32%" sorted={false}>
                      Title
                    </DataTableHeadCell>
                    <DataTableHeadCell align="center" width="10%" sorted={false}>
                      CEFR
                    </DataTableHeadCell>
                    <DataTableHeadCell align="center" width="14%" sorted={false}>
                      Skill
                    </DataTableHeadCell>
                    <DataTableHeadCell align="center" width="14%" sorted={false}>
                      Topic
                    </DataTableHeadCell>
                    <DataTableHeadCell width="18%" sorted={false}>
                      Source
                    </DataTableHeadCell>
                    <DataTableHeadCell align="right" width="12%" sorted={false}>
                      &nbsp;
                    </DataTableHeadCell>
                  </TableRow>
                </MDBox>
                <TableBody>
                  {items.map((item) => {
                    const cefrOk =
                      item.cefr_level &&
                      ["A1", "A2", "B1", "B2", "C1", "C2"].includes(item.cefr_level);
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
                          <MDButton
                            variant="gradient"
                            color="primary"
                            size="small"
                            onClick={() => setPreviewId(item.resource_id)}
                          >
                            Preview
                          </MDButton>
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

      <Footer />
    </DashboardLayout>
  );
}

export default BrowseResources;
