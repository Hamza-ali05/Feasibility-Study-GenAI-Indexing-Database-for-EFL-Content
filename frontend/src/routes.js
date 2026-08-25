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
import Experiments from "layouts/experiments";
import Analytics from "layouts/analytics";
import Duplicates from "layouts/duplicates";
import AdminOverview from "layouts/admin/overview";
import AdminManageResources from "layouts/admin/manage-resources";
import AdminLogs from "layouts/admin/logs";
import PractitionerOverview from "layouts/practitioner/overview";
import PractitionerManage from "layouts/practitioner/manage";
import ReportGenerator from "layouts/report";
import SecurityEvaluation from "layouts/security";
import FiguresPage from "layouts/figures";
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
import ScienceIcon from "@mui/icons-material/Science";
import QueryStatsIcon from "@mui/icons-material/QueryStats";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import AdminPanelSettingsIcon from "@mui/icons-material/AdminPanelSettings";
import GroupsIcon from "@mui/icons-material/Groups";
import PeopleIcon from "@mui/icons-material/People";
import DescriptionIcon from "@mui/icons-material/Description";
import SecurityIcon from "@mui/icons-material/Security";
import ImageIcon from "@mui/icons-material/Image";
import InfoIcon from "@mui/icons-material/Info";
import TravelExploreIcon from "@mui/icons-material/TravelExplore";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import MergeTypeIcon from "@mui/icons-material/MergeType";
import BarChartIcon from "@mui/icons-material/BarChart";
import CleaningServicesIcon from "@mui/icons-material/CleaningServices";
import CallSplitIcon from "@mui/icons-material/CallSplit";
import TuneIcon from "@mui/icons-material/Tune";
import BalanceIcon from "@mui/icons-material/Balance";
import ModelTrainingIcon from "@mui/icons-material/ModelTraining";
import FactCheckIcon from "@mui/icons-material/FactCheck";
import PublicIcon from "@mui/icons-material/Public";
import PlaceIcon from "@mui/icons-material/Place";
import VerifiedIcon from "@mui/icons-material/Verified";
import BoltIcon from "@mui/icons-material/Bolt";
import WorkspacesIcon from "@mui/icons-material/Workspaces";
import InsightsIcon from "@mui/icons-material/Insights";
import ManageAccountsIcon from "@mui/icons-material/ManageAccounts";

const routes = [
  {
    type: "collapse",
    name: "Dashboard",
    key: "dashboard",
    icon: <DashboardIcon fontSize="small" />,
    route: "/dashboard",
    component: <Dashboard />,
  },

  {
    type: "title",
    title: "EFL Workspace",
    key: "title-efl-workspace",
    icon: <WorkspacesIcon fontSize="small" />,
  },

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

  {
    type: "title",
    title: "Insights",
    key: "title-insights",
    icon: <InsightsIcon fontSize="small" />,
  },

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
    name: "Experiments",
    key: "experiments",
    icon: <ScienceIcon fontSize="small" />,
    route: "/experiments",
    component: <Experiments />,
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

  {
    type: "title",
    title: "Admin Panel",
    key: "title-admin",
    icon: <AdminPanelSettingsIcon fontSize="small" />,
  },

  {
    type: "collapse",
    name: "Overview",
    key: "admin-overview",
    icon: <AdminPanelSettingsIcon fontSize="small" />,
    route: "/admin/overview",
    component: (
      <RequireAuth>
        <AdminOverview />
      </RequireAuth>
    ),
  },
  {
    type: "collapse",
    name: "Manage Resources",
    key: "admin-resources",
    icon: <LibraryBooksIcon fontSize="small" />,
    route: "/admin/resources",
    component: (
      <RequireAuth>
        <AdminManageResources />
      </RequireAuth>
    ),
  },
  {
    type: "collapse",
    name: "Logs",
    key: "admin-logs",
    icon: <DescriptionIcon fontSize="small" />,
    route: "/admin/logs",
    component: (
      <RequireAuth>
        <AdminLogs />
      </RequireAuth>
    ),
  },
  {
    type: "collapse",
    name: "Practitioner Evaluation",
    key: "practitioner-overview",
    icon: <GroupsIcon fontSize="small" />,
    route: "/practitioner/overview",
    component: (
      <RequireAuth>
        <PractitionerOverview />
      </RequireAuth>
    ),
  },
  {
    type: "collapse",
    name: "Manage Participants",
    key: "practitioner-manage",
    icon: <PeopleIcon fontSize="small" />,
    route: "/practitioner/manage",
    component: (
      <RequireAuth>
        <PractitionerManage />
      </RequireAuth>
    ),
  },
  {
    type: "collapse",
    name: "Report Generator",
    key: "report-generator",
    icon: <DescriptionIcon fontSize="small" />,
    route: "/report",
    component: (
      <RequireAuth>
        <ReportGenerator />
      </RequireAuth>
    ),
  },
  {
    type: "collapse",
    name: "Security Audit",
    key: "security-audit",
    icon: <SecurityIcon fontSize="small" />,
    route: "/security",
    component: (
      <RequireAuth>
        <SecurityEvaluation />
      </RequireAuth>
    ),
  },
  {
    type: "collapse",
    name: "Project figures",
    key: "project-figures",
    icon: <ImageIcon fontSize="small" />,
    route: "/figures",
    component: (
      <RequireAuth>
        <FiguresPage />
      </RequireAuth>
    ),
  },

  {
    type: "title",
    title: "Pipeline",
    key: "title-pipeline",
    icon: <AccountTreeIcon fontSize="small" />,
  },

  {
    type: "collapse",
    name: "Discover",
    key: "pipeline-discover",
    icon: <TravelExploreIcon fontSize="small" />,
    route: "/pipeline/discover",
    component: <DiscoverStage />,
  },
  {
    type: "collapse",
    name: "Load",
    key: "pipeline-load",
    icon: <CloudUploadIcon fontSize="small" />,
    route: "/pipeline/load",
    component: <LoadStage />,
  },
  {
    type: "collapse",
    name: "Integrate",
    key: "pipeline-integrate",
    icon: <MergeTypeIcon fontSize="small" />,
    route: "/pipeline/integrate",
    component: <IntegrateStage />,
  },
  {
    type: "collapse",
    name: "EDA",
    key: "pipeline-eda",
    icon: <BarChartIcon fontSize="small" />,
    route: "/pipeline/eda",
    component: <EDAStage />,
  },
  {
    type: "collapse",
    name: "Clean",
    key: "pipeline-clean",
    icon: <CleaningServicesIcon fontSize="small" />,
    route: "/pipeline/clean",
    component: <CleanStage />,
  },
  {
    type: "collapse",
    name: "Split",
    key: "pipeline-split",
    icon: <CallSplitIcon fontSize="small" />,
    route: "/pipeline/split",
    component: <SplitStage />,
  },
  {
    type: "collapse",
    name: "Preprocess",
    key: "pipeline-preprocess",
    icon: <TuneIcon fontSize="small" />,
    route: "/pipeline/preprocess",
    component: <PreprocessStage />,
  },
  {
    type: "collapse",
    name: "Balance",
    key: "pipeline-balance",
    icon: <BalanceIcon fontSize="small" />,
    route: "/pipeline/balance",
    component: <BalanceStage />,
  },
  {
    type: "collapse",
    name: "Train",
    key: "pipeline-train",
    icon: <ModelTrainingIcon fontSize="small" />,
    route: "/pipeline/train",
    component: <TrainStage />,
  },
  {
    type: "collapse",
    name: "Evaluate",
    key: "pipeline-evaluate",
    icon: <FactCheckIcon fontSize="small" />,
    route: "/pipeline/evaluate",
    component: <EvaluateStage />,
  },
  {
    type: "collapse",
    name: "Explain Global",
    key: "pipeline-explain-global",
    icon: <PublicIcon fontSize="small" />,
    route: "/pipeline/explain-global",
    component: <ExplainGlobalStage />,
  },
  {
    type: "collapse",
    name: "Explain Local",
    key: "pipeline-explain-local",
    icon: <PlaceIcon fontSize="small" />,
    route: "/pipeline/explain-local",
    component: <ExplainLocalStage />,
  },
  {
    type: "collapse",
    name: "Explain Quality",
    key: "pipeline-explain-quality",
    icon: <VerifiedIcon fontSize="small" />,
    route: "/pipeline/explain-quality",
    component: <ExplainQualityStage />,
  },
  {
    type: "collapse",
    name: "Predict",
    key: "pipeline-predict",
    icon: <BoltIcon fontSize="small" />,
    route: "/pipeline/predict",
    component: <PredictStage />,
  },

  {
    type: "title",
    title: "Account",
    key: "title-account",
    icon: <ManageAccountsIcon fontSize="small" />,
  },

  {
    type: "hidden",
    name: "Sign In",
    key: "sign-in",
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
