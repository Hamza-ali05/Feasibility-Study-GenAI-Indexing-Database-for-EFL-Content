/**
=========================================================
* EFL IndexDB - v2.2.0
* EFL IndexDB navigation (Prompt 4-D)
=========================================================

* Product Page: https://www.creative-tim.com/product/material-dashboard-react
* Copyright 2023 Creative Tim (https://www.creative-tim.com)

Coded by www.creative-tim.com

 =========================================================

* The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
*/

import Dashboard from "layouts/dashboard";
import SignIn from "layouts/authentication/sign-in";
import Search from "layouts/search";
import AskAI from "layouts/ask-ai";
import BrowseResources from "layouts/resources";
import Analyzer from "layouts/analyzer";
import DiscoverStage from "layouts/pipeline/Discover";
import LoadStage from "layouts/pipeline/Load";
import IntegrateStage from "layouts/pipeline/Integrate";
import EDAStage from "layouts/pipeline/EDA";
import CleanStage from "layouts/pipeline/Clean";
import SplitStage from "layouts/pipeline/Split";
import PreprocessStage from "layouts/pipeline/Preprocess";
import BalanceStage from "layouts/pipeline/Balance";
import TrainStage from "layouts/pipeline/Train";
import EvaluateStage from "layouts/pipeline/Evaluate";
import ExplainGlobalStage from "layouts/pipeline/ExplainGlobal";
import ExplainLocalStage from "layouts/pipeline/ExplainLocal";
import ExplainQualityStage from "layouts/pipeline/ExplainQuality";
import PredictStage from "layouts/pipeline/Predict";
import Metrics from "layouts/metrics";
import Analytics from "layouts/analytics";
import Duplicates from "layouts/duplicates";
import AdminOverview from "layouts/admin/overview";
import AdminManageResources from "layouts/admin/manage-resources";
import AdminLogs from "layouts/admin/logs";
import About from "layouts/about";
import RecommendationsPage from "layouts/recommendations";

import RequireAuth from "components/EflShared/RequireAuth";

import DashboardIcon from "@mui/icons-material/Dashboard";
import SearchIcon from "@mui/icons-material/Search";
import ChatBubbleOutlineIcon from "@mui/icons-material/ChatBubbleOutline";
import LibraryBooksIcon from "@mui/icons-material/LibraryBooks";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import AccountTreeIcon from "@mui/icons-material/AccountTree";
import AssessmentIcon from "@mui/icons-material/Assessment";
import QueryStatsIcon from "@mui/icons-material/QueryStats";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import AdminPanelSettingsIcon from "@mui/icons-material/AdminPanelSettings";
import LoginIcon from "@mui/icons-material/Login";
import InfoIcon from "@mui/icons-material/Info";
import FiberManualRecordIcon from "@mui/icons-material/FiberManualRecord";

const nestIcon = <FiberManualRecordIcon sx={{ fontSize: "0.55rem !important" }} />;

const routes = [
  {
    type: "collapse",
    name: "Dashboard",
    key: "dashboard",
    icon: <DashboardIcon fontSize="small" />,
    route: "/dashboard",
    component: <Dashboard />,
  },

  { type: "title", title: "EFL Workspace", key: "title-efl-workspace" },

  {
    type: "collapse",
    name: "Search",
    key: "search",
    icon: <SearchIcon fontSize="small" />,
    route: "/search",
    component: <Search />,
  },
  {
    type: "collapse",
    name: "Ask AI",
    key: "ask-ai",
    icon: <ChatBubbleOutlineIcon fontSize="small" />,
    route: "/ask-ai",
    component: <AskAI />,
  },
  {
    type: "collapse",
    name: "Browse Resources",
    key: "resources",
    icon: <LibraryBooksIcon fontSize="small" />,
    route: "/resources",
    component: <BrowseResources />,
  },

  {
    type: "hidden",
    name: "Recommendations",
    key: "recommendations",
    route: "/recommendations/:resourceId",
    component: <RecommendationsPage />,
  },
  {
    type: "collapse",
    name: "Resource Analyzer",
    key: "analyzer",
    icon: <UploadFileIcon fontSize="small" />,
    route: "/analyzer",
    component: <Analyzer />,
  },

  { type: "title", title: "Pipeline", key: "title-pipeline" },

  {
    type: "collapse",
    name: "Pipeline Monitor",
    key: "pipeline-monitor",
    icon: <AccountTreeIcon fontSize="small" />,
    collapse: [
      {
        name: "Discover",
        key: "pipeline-discover",
        icon: nestIcon,
        route: "/pipeline/discover",
        component: <DiscoverStage />,
      },
      {
        name: "Load",
        key: "pipeline-load",
        icon: nestIcon,
        route: "/pipeline/load",
        component: <LoadStage />,
      },
      {
        name: "Integrate",
        key: "pipeline-integrate",
        icon: nestIcon,
        route: "/pipeline/integrate",
        component: <IntegrateStage />,
      },
      {
        name: "EDA",
        key: "pipeline-eda",
        icon: nestIcon,
        route: "/pipeline/eda",
        component: <EDAStage />,
      },
      {
        name: "Clean",
        key: "pipeline-clean",
        icon: nestIcon,
        route: "/pipeline/clean",
        component: <CleanStage />,
      },
      {
        name: "Split",
        key: "pipeline-split",
        icon: nestIcon,
        route: "/pipeline/split",
        component: <SplitStage />,
      },
      {
        name: "Preprocess",
        key: "pipeline-preprocess",
        icon: nestIcon,
        route: "/pipeline/preprocess",
        component: <PreprocessStage />,
      },
      {
        name: "Balance",
        key: "pipeline-balance",
        icon: nestIcon,
        route: "/pipeline/balance",
        component: <BalanceStage />,
      },
      {
        name: "Train",
        key: "pipeline-train",
        icon: nestIcon,
        route: "/pipeline/train",
        component: <TrainStage />,
      },
      {
        name: "Evaluate",
        key: "pipeline-evaluate",
        icon: nestIcon,
        route: "/pipeline/evaluate",
        component: <EvaluateStage />,
      },
      {
        name: "Explain Global",
        key: "pipeline-explain-global",
        icon: nestIcon,
        route: "/pipeline/explain-global",
        component: <ExplainGlobalStage />,
      },
      {
        name: "Explain Local",
        key: "pipeline-explain-local",
        icon: nestIcon,
        route: "/pipeline/explain-local",
        component: <ExplainLocalStage />,
      },
      {
        name: "Explain Quality",
        key: "pipeline-explain-quality",
        icon: nestIcon,
        route: "/pipeline/explain-quality",
        component: <ExplainQualityStage />,
      },
      {
        name: "Predict",
        key: "pipeline-predict",
        icon: nestIcon,
        route: "/pipeline/predict",
        component: <PredictStage />,
      },
    ],
  },

  { type: "title", title: "Insights", key: "title-insights" },

  {
    type: "collapse",
    name: "Metrics",
    key: "metrics",
    icon: <AssessmentIcon fontSize="small" />,
    route: "/metrics",
    component: <Metrics />,
  },
  {
    type: "collapse",
    name: "Search Analytics",
    key: "analytics",
    icon: <QueryStatsIcon fontSize="small" />,
    route: "/analytics",
    component: <Analytics />,
  },
  {
    type: "collapse",
    name: "Duplicate Detection",
    key: "duplicates",
    icon: <ContentCopyIcon fontSize="small" />,
    route: "/duplicates",
    component: <Duplicates />,
  },

  { type: "title", title: "Admin", key: "title-admin" },

  {
    type: "collapse",
    name: "Admin Panel",
    key: "admin-panel",
    icon: <AdminPanelSettingsIcon fontSize="small" />,
    collapse: [
      {
        name: "Overview",
        key: "admin-overview",
        icon: nestIcon,
        route: "/admin/overview",
        component: (
          <RequireAuth>
            <AdminOverview />
          </RequireAuth>
        ),
      },
      {
        name: "Manage Resources",
        key: "admin-resources",
        icon: nestIcon,
        route: "/admin/resources",
        component: (
          <RequireAuth>
            <AdminManageResources />
          </RequireAuth>
        ),
      },
      {
        name: "Logs",
        key: "admin-logs",
        icon: nestIcon,
        route: "/admin/logs",
        component: (
          <RequireAuth>
            <AdminLogs />
          </RequireAuth>
        ),
      },
    ],
  },

  { type: "title", title: "Account", key: "title-account" },

  {
    type: "collapse",
    name: "Sign In",
    key: "sign-in",
    icon: <LoginIcon fontSize="small" />,
    route: "/authentication/sign-in",
    component: <SignIn />,
  },
  {
    type: "collapse",
    name: "About",
    key: "about",
    icon: <InfoIcon fontSize="small" />,
    route: "/about",
    component: <About />,
  },
];

export default routes;
