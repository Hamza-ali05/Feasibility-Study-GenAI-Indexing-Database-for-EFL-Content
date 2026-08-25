import { useCallback, useEffect, useRef, useState } from "react";
import { Link as RouterLink, useSearchParams } from "react-router-dom";

import Card from "@mui/material/Card";
import Chip from "@mui/material/Chip";
import FormControl from "@mui/material/FormControl";
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

/** Canonical CEFR levels used by the CEFR classifier / pipeline. */
const CEFR_OPTIONS = [
  { value: "A1", label: "A1 — Beginner" },
  { value: "A2", label: "A2 — Elementary" },
  { value: "B1", label: "B1 — Intermediate" },
  { value: "B2", label: "B2 — Upper intermediate" },
  { value: "C1", label: "C1 — Advanced" },
  { value: "C2", label: "C2 — Proficiency" },
];

/** Skill types used by analyzer / resource labeling. */
const SKILL_OPTIONS = [
  { value: "Reading", label: "Reading" },
  { value: "Writing", label: "Writing" },
  { value: "Listening", label: "Listening" },
  { value: "Speaking", label: "Speaking" },
  { value: "Grammar", label: "Grammar" },
  { value: "Vocabulary", label: "Vocabulary" },
];

/** Topic domains used by analyzer / resource labeling. */
const TOPIC_OPTIONS = [
  { value: "Business", label: "Business" },
  { value: "Science", label: "Science" },
  { value: "Culture", label: "Culture" },
  { value: "Technology", label: "Technology" },
  { value: "Daily Life", label: "Daily life" },
  { value: "Academic", label: "Academic" },
  { value: "Travel", label: "Travel" },
  { value: "Health", label: "Health" },
];

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

/**
 * Merge trained taxonomy with live facet counts.
 * Always shows canonical values even when metadata facets are empty.
 */
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
    async (overrideQuery, filterOverrides = null) => {
      const typed = (overrideQuery !== undefined ? overrideQuery : query).trim();
      const nextCefr =
        filterOverrides && Object.prototype.hasOwnProperty.call(filterOverrides, "cefrLevel")
          ? filterOverrides.cefrLevel
          : cefrLevel;
      const nextSkill =
        filterOverrides && Object.prototype.hasOwnProperty.call(filterOverrides, "skillType")
          ? filterOverrides.skillType
          : skillType;
      const nextTopic =
        filterOverrides && Object.prototype.hasOwnProperty.call(filterOverrides, "topicDomain")
          ? filterOverrides.topicDomain
          : topicDomain;
      const hasFilters = Boolean(nextCefr || nextSkill || nextTopic);

      if (!typed && !hasFilters) {
        setError("Enter a search query, or choose at least one filter (CEFR, skill, or topic).");
        return;
      }

      setLoading(true);
      setError(null);
      setPipelineAlert(false);
      setShowSuggestions(false);

      try {
        const payload = {
          query: typed,
          top_k: 10,
        };
        if (nextCefr) payload.cefr_level = nextCefr;
        if (nextSkill) payload.skill_type = nextSkill;
        if (nextTopic) payload.topic_domain = nextTopic;

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
        const next = (Array.isArray(list) ? list : [])
          .map((item) => (typeof item === "string" ? item : item?.title || ""))
          .map((t) => String(t).trim())
          .filter(Boolean)
          .slice(0, 5);
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
    const selected = String(title || "").trim();
    if (!selected) return;
    if (suggestTimer.current) clearTimeout(suggestTimer.current);
    suggestSeq.current += 1;
    setQuery(selected);
    setShowSuggestions(false);
    setSuggestions([]);
    runSearch(selected);
  };

  const handleKeyDown = (event) => {
    if (event.key === "Escape") {
      setShowSuggestions(false);
      return;
    }
    if (event.key === "ArrowDown" && suggestions.length > 0) {
      event.preventDefault();
      setShowSuggestions(true);
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      setShowSuggestions(false);
      runSearch();
    }
  };

  const cefrOpts = buildFilterOptions(CEFR_OPTIONS, facets.cefr_level);
  const skillOpts = buildFilterOptions(SKILL_OPTIONS, facets.skill_type);
  const topicOpts = buildFilterOptions(TOPIC_OPTIONS, facets.topic_domain);

  return (
    <DashboardLayout>
      <DashboardNavbar />
      <MDBox py={3}>
        <MDBox mb={3} px={0.5}>
          <MDTypography variant="h4" fontWeight="bold">
            Search
          </MDTypography>
          <MDTypography variant="button" color="text">
            Semantic search across indexed EFL resources
          </MDTypography>
        </MDBox>
        <Card sx={{ p: 2, mb: 2, position: "relative", zIndex: 2 }}>
          <ClickAwayListener onClickAway={() => setShowSuggestions(false)}>
            <MDBox position="relative" zIndex={showSuggestions ? 40 : 1}>
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
                    autoComplete="off"
                    placeholder="e.g. grammar exercises A2"
                    inputProps={{
                      "aria-autocomplete": "list",
                      "aria-expanded": showSuggestions,
                      role: "combobox",
                    }}
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

              {showSuggestions && suggestions.length > 0 && (
                <Paper
                  elevation={8}
                  role="listbox"
                  sx={{
                    position: "absolute",
                    left: 0,
                    right: { xs: 0, sm: "7rem" },
                    top: "100%",
                    mt: 0.5,
                    zIndex: 50,
                    maxHeight: 280,
                    overflowY: "auto",
                    bgcolor: "background.paper",
                  }}
                >
                  <List dense disablePadding>
                    {suggestions.map((title, index) => (
                      <ListItemButton
                        key={`${title}-${index}`}
                        role="option"
                        dense
                        sx={{ cursor: "pointer", py: 1.1 }}
                        // mousedown: select before blur/click-away unmounts the list
                        onMouseDown={(event) => {
                          event.preventDefault();
                          event.stopPropagation();
                          pickSuggestion(title);
                        }}
                      >
                        <ListItemText
                          primary={title}
                          primaryTypographyProps={{ variant: "body2", noWrap: true }}
                        />
                      </ListItemButton>
                    ))}
                  </List>
                </Paper>
              )}
            </MDBox>
          </ClickAwayListener>

          <Grid container spacing={2} mt={1} alignItems="flex-end">
            <Grid item xs={12} sm={4} md={3}>
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
                  onChange={(e) => setCefrLevel(e.target.value)}
                  renderValue={(selected) => {
                    if (!selected) return "Any level";
                    const match = cefrOpts.find((o) => o.value === selected);
                    return match?.label || selected;
                  }}
                  MenuProps={{
                    PaperProps: {
                      sx: {
                        maxHeight: 280,
                        overflowY: "auto",
                      },
                    },
                    anchorOrigin: { vertical: "bottom", horizontal: "left" },
                    transformOrigin: { vertical: "top", horizontal: "left" },
                  }}
                  sx={{
                    "& .MuiSelect-select": {
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    },
                  }}
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
            <Grid item xs={12} sm={4} md={3}>
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
                  onChange={(e) => setSkillType(e.target.value)}
                  renderValue={(selected) => {
                    if (!selected) return "Any skill";
                    const match = skillOpts.find((o) => o.value === selected);
                    return match?.label || selected;
                  }}
                  MenuProps={{
                    PaperProps: {
                      sx: {
                        maxHeight: 280,
                        overflowY: "auto",
                      },
                    },
                    anchorOrigin: { vertical: "bottom", horizontal: "left" },
                    transformOrigin: { vertical: "top", horizontal: "left" },
                  }}
                  sx={{
                    "& .MuiSelect-select": {
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    },
                  }}
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
            <Grid item xs={12} sm={4} md={3}>
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
                  onChange={(e) => setTopicDomain(e.target.value)}
                  renderValue={(selected) => {
                    if (!selected) return "Any topic";
                    const match = topicOpts.find((o) => o.value === selected);
                    return match?.label || selected;
                  }}
                  MenuProps={{
                    PaperProps: {
                      sx: {
                        maxHeight: 280,
                        overflowY: "auto",
                      },
                    },
                    anchorOrigin: { vertical: "bottom", horizontal: "left" },
                    transformOrigin: { vertical: "top", horizontal: "left" },
                  }}
                  sx={{
                    "& .MuiSelect-select": {
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    },
                  }}
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
                  sx={{ borderColor: colors.grey[300], mb: 0.25 }}
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

        {!loading && results && results.length === 0 && !pipelineAlert && !error && (
          <Card
            sx={{
              p: { xs: 3, md: 4 },
              textAlign: "center",
              background: `linear-gradient(165deg, ${colors.grey[100]} 0%, #fff 55%, ${colors.grey[200]} 100%)`,
              border: `1px solid ${colors.grey[300]}`,
            }}
          >
            <MDBox
              mx="auto"
              mb={2}
              display="flex"
              alignItems="center"
              justifyContent="center"
              sx={{
                width: 64,
                height: 64,
                borderRadius: "50%",
                backgroundColor: colors.info.main,
                color: colors.white.main,
                fontSize: "1.5rem",
                fontWeight: 700,
                letterSpacing: "0.04em",
              }}
            >
              0
            </MDBox>
            <MDTypography variant="h5" fontWeight="bold" gutterBottom>
              No matching resources
            </MDTypography>
            <MDTypography variant="body2" color="text" sx={{ maxWidth: 480, mx: "auto", mb: 2 }}>
              {filtersActive
                ? "Nothing in the index matches this combination of filters yet. Try clearing one filter, broadening the CEFR level, or adding a short search phrase."
                : "We could not find resources for that query. Try different keywords, or use CEFR / skill / topic filters to browse the collection."}
            </MDTypography>
            {(filtersActive || Boolean(query.trim())) && (
              <MDBox display="flex" flexWrap="wrap" gap={1} justifyContent="center" mb={2.5}>
                {query.trim() && (
                  <Chip size="small" label={`Query: ${query.trim()}`} variant="outlined" />
                )}
                {cefrLevel && (
                  <Chip
                    size="small"
                    label={CEFR_OPTIONS.find((o) => o.value === cefrLevel)?.label || cefrLevel}
                    color="info"
                    variant="outlined"
                  />
                )}
                {skillType && (
                  <Chip size="small" label={skillType} color="info" variant="outlined" />
                )}
                {topicDomain && (
                  <Chip size="small" label={topicDomain} color="info" variant="outlined" />
                )}
              </MDBox>
            )}
            <MDBox display="flex" gap={1} justifyContent="center" flexWrap="wrap">
              {filtersActive && (
                <MDButton variant="outlined" color="dark" size="small" onClick={clearFilters}>
                  Clear filters
                </MDButton>
              )}
              <MDButton
                variant="gradient"
                color="info"
                size="small"
                onClick={() => {
                  const sample = "english reading practice";
                  setQuery(sample);
                  setCefrLevel("");
                  setSkillType("Reading");
                  setTopicDomain("");
                  runSearch(sample, {
                    cefrLevel: "",
                    skillType: "Reading",
                    topicDomain: "",
                  });
                }}
              >
                Try a sample search
              </MDButton>
            </MDBox>
          </Card>
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
