import { useCallback, useEffect, useRef, useState } from "react";
import { Link as RouterLink, useSearchParams } from "react-router-dom";

import Card from "@mui/material/Card";
import Chip from "@mui/material/Chip";
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Skeleton from "@mui/material/Skeleton";
import ClickAwayListener from "@mui/material/ClickAwayListener";
import Paper from "@mui/material/Paper";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemText from "@mui/material/ListItemText";
import Grid from "@mui/material/Grid";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDInput from "components/MDInput";
import MDButton from "components/MDButton";
import MDAlert from "components/MDAlert";

import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";

import DocumentPreviewModal from "components/EflShared/DocumentPreviewModal";
import SearchResultCard from "layouts/search/SearchResultCard";

import { getSearchFacets, getSuggestions, searchResources } from "services/endpoints";
import colors from "assets/theme/base/colors";

const SUGGEST_DEBOUNCE_MS = 250;

function facetOptions(facetMap) {
  if (!facetMap || typeof facetMap !== "object") return [];
  return Object.entries(facetMap)
    .map(([value, count]) => ({ value, count: Number(count) || 0 }))
    .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value));
}

function Search() {
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState(() => searchParams.get("q") || "");
  const [cefrLevel, setCefrLevel] = useState("");
  const [skillType, setSkillType] = useState("");
  const [topicDomain, setTopicDomain] = useState("");

  const [facets, setFacets] = useState({
    cefr_level: {},
    skill_type: {},
    topic_domain: {},
  });

  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [queryCefr, setQueryCefr] = useState(null);
  const [pipelineAlert, setPipelineAlert] = useState(false);
  const [error, setError] = useState(null);

  const [previewId, setPreviewId] = useState(null);

  const suggestTimer = useRef(null);
  const suggestSeq = useRef(0);

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
      } catch (err) {}
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const filtersActive = Boolean(cefrLevel || skillType || topicDomain);

  const clearFilters = () => {
    setCefrLevel("");
    setSkillType("");
    setTopicDomain("");
  };

  const runSearch = useCallback(
    async (overrideQuery) => {
      const q = (overrideQuery !== undefined ? overrideQuery : query).trim();
      if (!q) {
        setError("Enter a search query.");
        return;
      }

      setLoading(true);
      setError(null);
      setPipelineAlert(false);
      setShowSuggestions(false);

      try {
        const payload = {
          query: q,
          top_k: 10,
        };
        if (cefrLevel) payload.cefr_level = cefrLevel;
        if (skillType) payload.skill_type = skillType;
        if (topicDomain) payload.topic_domain = topicDomain;

        const data = await searchResources(payload);
        setResults(Array.isArray(data?.results) ? data.results : []);
        setQueryCefr(data?.query_cefr_prediction || null);
      } catch (err) {
        const status = err?.response?.status;
        if (status === 503) {
          setPipelineAlert(true);
          setResults([]);
          setQueryCefr(null);
        } else {
          const detail = err?.response?.data?.detail || err?.message || "Search failed";
          setError(typeof detail === "string" ? detail : JSON.stringify(detail));
          setResults([]);
          setQueryCefr(null);
        }
      } finally {
        setLoading(false);
      }
    },
    [query, cefrLevel, skillType, topicDomain]
  );

  const bootstrappedQ = useRef(false);
  useEffect(() => {
    const q = (searchParams.get("q") || "").trim();
    if (!q || bootstrappedQ.current) return;
    bootstrappedQ.current = true;
    setQuery(q);
    runSearch(q);
  }, [searchParams, runSearch]);

  const scheduleSuggestions = (value) => {
    if (suggestTimer.current) clearTimeout(suggestTimer.current);
    const q = value.trim();
    if (!q) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    const seq = ++suggestSeq.current;
    suggestTimer.current = setTimeout(async () => {
      try {
        const list = await getSuggestions(q);
        if (seq !== suggestSeq.current) return;
        const next = Array.isArray(list) ? list.slice(0, 5) : [];
        setSuggestions(next);
        setShowSuggestions(next.length > 0);
      } catch (err) {
        if (seq === suggestSeq.current) {
          setSuggestions([]);
          setShowSuggestions(false);
        }
      }
    }, SUGGEST_DEBOUNCE_MS);
  };

  const handleQueryChange = (event) => {
    const value = event.target.value;
    setQuery(value);
    scheduleSuggestions(value);
  };

  const pickSuggestion = (title) => {
    setQuery(title);
    setShowSuggestions(false);
    setSuggestions([]);
    runSearch(title);
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      runSearch();
    }
  };

  const cefrOpts = facetOptions(facets.cefr_level);
  const skillOpts = facetOptions(facets.skill_type);
  const topicOpts = facetOptions(facets.topic_domain);

  return (
    <DashboardLayout>
      <DashboardNavbar />
      <MDBox py={3}>
        <MDTypography variant="h4" fontWeight="bold" mb={0.5}>
          AI Semantic Search
        </MDTypography>
        <MDTypography variant="button" color="text" mb={3} display="block">
          Search the indexed EFL corpus with Smart Filters
        </MDTypography>

        <Card sx={{ p: 2, mb: 2, position: "relative", zIndex: 2 }}>
          <ClickAwayListener onClickAway={() => setShowSuggestions(false)}>
            <MDBox position="relative">
              <MDBox display="flex" gap={1} alignItems="flex-start">
                <MDBox flex={1}>
                  <MDInput
                    type="search"
                    label="Search resources"
                    fullWidth
                    value={query}
                    onChange={handleQueryChange}
                    onKeyDown={handleKeyDown}
                    onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
                    placeholder="e.g. grammar exercises A2"
                  />
                </MDBox>
                <MDButton
                  variant="gradient"
                  color="primary"
                  onClick={() => runSearch()}
                  disabled={loading}
                >
                  Search
                </MDButton>
              </MDBox>

              {showSuggestions && (
                <Paper
                  elevation={4}
                  sx={{
                    position: "absolute",
                    left: 0,
                    right: { xs: 0, sm: "7rem" },
                    top: "100%",
                    mt: 0.5,
                    zIndex: 20,
                    maxHeight: 240,
                    overflowY: "auto",
                  }}
                >
                  <List dense disablePadding>
                    {suggestions.map((title) => (
                      <ListItemButton key={title} onClick={() => pickSuggestion(title)}>
                        <ListItemText
                          primary={title}
                          primaryTypographyProps={{ variant: "body2" }}
                        />
                      </ListItemButton>
                    ))}
                  </List>
                </Paper>
              )}
            </MDBox>
          </ClickAwayListener>

          <Grid container spacing={2} mt={0.5} alignItems="center">
            <Grid item xs={12} sm={4} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel id="filter-cefr">CEFR level</InputLabel>
                <Select
                  labelId="filter-cefr"
                  label="CEFR level"
                  value={cefrLevel}
                  onChange={(e) => setCefrLevel(e.target.value)}
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
                <InputLabel id="filter-skill">Skill type</InputLabel>
                <Select
                  labelId="filter-skill"
                  label="Skill type"
                  value={skillType}
                  onChange={(e) => setSkillType(e.target.value)}
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
                <InputLabel id="filter-topic">Topic domain</InputLabel>
                <Select
                  labelId="filter-topic"
                  label="Topic domain"
                  value={topicDomain}
                  onChange={(e) => setTopicDomain(e.target.value)}
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
                  sx={{ borderColor: colors.grey[300] }}
                  variant="outlined"
                />
              </Grid>
            )}
          </Grid>
        </Card>

        {pipelineAlert && (
          <MDBox mb={2}>
            <MDAlert color="warning">
              <MDBox display="flex" flexDirection="column" gap={1} width="100%">
                <MDTypography variant="button" color="white">
                  The indexing pipeline hasn&apos;t finished yet — visit Pipeline Monitor to run it.
                </MDTypography>
                <MDBox>
                  <MDButton
                    component={RouterLink}
                    to="/pipeline/discover"
                    variant="outlined"
                    color="white"
                    size="small"
                  >
                    Open Pipeline Monitor
                  </MDButton>
                </MDBox>
              </MDBox>
            </MDAlert>
          </MDBox>
        )}

        {error && (
          <MDBox mb={2}>
            <MDAlert color="error">{error}</MDAlert>
          </MDBox>
        )}

        {queryCefr && !loading && (
          <MDBox
            mb={2}
            px={2}
            py={1.25}
            borderRadius="md"
            sx={{
              backgroundColor: colors.grey[100],
              border: `1px solid ${colors.grey[300]}`,
            }}
          >
            <MDTypography variant="button" fontWeight="medium">
              Estimated level of your query: {queryCefr}
            </MDTypography>
          </MDBox>
        )}

        {loading && (
          <MDBox>
            {[0, 1, 2].map((i) => (
              <Card key={i} sx={{ mb: 2, p: 2 }}>
                <Skeleton width="60%" height={28} />
                <Skeleton width="40%" height={20} sx={{ mt: 1 }} />
                <Skeleton width="100%" height={12} sx={{ mt: 2 }} />
                <Skeleton width="30%" height={18} sx={{ mt: 1 }} />
              </Card>
            ))}
          </MDBox>
        )}

        {!loading && results && results.length === 0 && !pipelineAlert && (
          <MDTypography variant="button" color="text">
            No results. Try a broader query or clear filters.
          </MDTypography>
        )}

        {!loading &&
          results &&
          results.map((hit) => (
            <SearchResultCard key={hit.resource_id} result={hit} onPreview={setPreviewId} />
          ))}
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

export default Search;
