import { useCallback, useEffect, useMemo, useState } from "react";

import { useLocation, NavLink } from "react-router-dom";

import PropTypes from "prop-types";

import List from "@mui/material/List";
import Divider from "@mui/material/Divider";
import Link from "@mui/material/Link";
import Icon from "@mui/material/Icon";
import MuiCollapse from "@mui/material/Collapse";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";

import SidenavCollapse from "examples/Sidenav/SidenavCollapse";

import SidenavRoot from "examples/Sidenav/SidenavRoot";
import sidenavLogoLabel from "examples/Sidenav/styles/sidenav";

import {
  useMaterialUIController,
  setMiniSidenav,
  setTransparentSidenav,
  setWhiteSidenav,
} from "context";

function pathMatches(pathname, route) {
  if (!route) return false;
  const base = route.split("/:")[0];
  return pathname === route || pathname === base || pathname.startsWith(`${base}/`);
}

function routeIsActive(pathname, routeItem) {
  if (!routeItem) return false;
  if (routeItem.route && pathMatches(pathname, routeItem.route)) return true;
  if (Array.isArray(routeItem.collapse)) {
    return routeItem.collapse.some((c) => pathMatches(pathname, c.route));
  }
  return false;
}

/** Split flat routes into title sections for expand/collapse groups. */
function buildSections(routes) {
  const sections = [];
  let current = { key: "section-top", title: null, icon: null, items: [] };

  routes.forEach((route) => {
    if (route.type === "hidden") return;
    if (route.type === "title") {
      if (current.items.length || current.title) {
        sections.push(current);
      }
      current = {
        key: route.key,
        title: route.title,
        icon: route.icon || null,
        items: [],
      };
      return;
    }
    current.items.push(route);
  });

  if (current.items.length || current.title) {
    sections.push(current);
  }
  return sections;
}

function Sidenav({ color, brand, brandName, routes, ...rest }) {
  const [controller, dispatch] = useMaterialUIController();
  const { miniSidenav, transparentSidenav, whiteSidenav, darkMode } = controller;
  const location = useLocation();
  const { pathname } = location;

  const sections = useMemo(() => buildSections(routes), [routes]);

  const [openSections, setOpenSections] = useState({});
  const [openNested, setOpenNested] = useState({});

  // Brand / logo text: white on dark sidebar, dark on light sidebar
  const darkSidenav = !whiteSidenav && !(transparentSidenav && !darkMode);
  const textColor = darkSidenav ? "white" : "dark";

  const closeSidenav = () => setMiniSidenav(dispatch, true);

  const toggleSection = useCallback((sectionKey) => {
    setOpenSections((prev) => ({ ...prev, [sectionKey]: !prev[sectionKey] }));
  }, []);

  const toggleNested = useCallback((key) => {
    setOpenNested((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  // Menus stay closed until the user opens them (no auto-expand on route change)

  useEffect(() => {
    function handleMiniSidenav() {
      setMiniSidenav(dispatch, window.innerWidth < 1200);
      setTransparentSidenav(dispatch, window.innerWidth < 1200 ? false : transparentSidenav);
      setWhiteSidenav(dispatch, window.innerWidth < 1200 ? false : whiteSidenav);
    }

    window.addEventListener("resize", handleMiniSidenav);
    handleMiniSidenav();
    return () => window.removeEventListener("resize", handleMiniSidenav);
  }, [dispatch, location, transparentSidenav, whiteSidenav]);

  const renderMenuItem = (routeItem) => {
    const { type, name, icon, noCollapse, key, href, route, collapse } = routeItem;

    if (type === "divider") {
      return (
        <Divider
          key={key}
          light={
            (!darkMode && !whiteSidenav && !transparentSidenav) ||
            (darkMode && !transparentSidenav && whiteSidenav)
          }
        />
      );
    }

    if (type !== "collapse") return null;

    // Parent with submenus — click toggles all children open/closed
    if (Array.isArray(collapse) && collapse.length > 0) {
      const isOpen = Boolean(openNested[key]);
      const childActive = collapse.some((c) => pathMatches(pathname, c.route));

      return (
        <MDBox key={key}>
          <SidenavCollapse
            name={name}
            icon={icon}
            active={childActive}
            open={isOpen}
            collapsible
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              toggleNested(key);
            }}
          />
          <MuiCollapse in={isOpen} timeout="auto" unmountOnExit>
            <List
              component="div"
              disablePadding
              sx={{
                pl: miniSidenav ? 0 : 1.5,
                "& .MuiListItem-root .MuiBox-root": {
                  marginLeft: miniSidenav ? undefined : "1.5rem",
                  marginRight: "1rem",
                },
              }}
            >
              {collapse.map((child) => (
                <NavLink
                  key={child.key}
                  to={child.route}
                  onClick={() => {
                    if (window.innerWidth < 1200) closeSidenav();
                  }}
                >
                  <SidenavCollapse
                    name={child.name}
                    icon={child.icon}
                    active={pathMatches(pathname, child.route)}
                  />
                </NavLink>
              ))}
            </List>
          </MuiCollapse>
        </MDBox>
      );
    }

    if (href) {
      return (
        <Link
          href={href}
          key={key}
          target="_blank"
          rel="noreferrer"
          sx={{ textDecoration: "none" }}
        >
          <SidenavCollapse
            name={name}
            icon={icon}
            active={pathMatches(pathname, route)}
            noCollapse={noCollapse}
          />
        </Link>
      );
    }

    return (
      <NavLink
        key={key}
        to={route}
        onClick={() => {
          if (window.innerWidth < 1200) closeSidenav();
        }}
      >
        <SidenavCollapse name={name} icon={icon} active={pathMatches(pathname, route)} />
      </NavLink>
    );
  };

  const renderSections = sections.map((section) => {
    // Titled menus start closed; only open after the user clicks
    const isSectionOpen = section.title ? Boolean(openSections[section.key]) : true;
    const sectionActive = section.items.some((item) => routeIsActive(pathname, item));

    return (
      <MDBox key={section.key} mb={0.5}>
        {section.title && (
          <SidenavCollapse
            name={section.title}
            icon={section.icon || <Icon fontSize="small">folder</Icon>}
            active={sectionActive}
            open={isSectionOpen}
            collapsible
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              toggleSection(section.key);
            }}
          />
        )}

        <MuiCollapse in={isSectionOpen} timeout="auto" unmountOnExit>
          <List
            component="div"
            disablePadding
            sx={
              section.title
                ? {
                    pl: miniSidenav ? 0 : 1,
                  }
                : undefined
            }
          >
            {section.items.map((item) => renderMenuItem(item))}
          </List>
        </MuiCollapse>
      </MDBox>
    );
  });

  return (
    <SidenavRoot
      {...rest}
      variant="permanent"
      ownerState={{ transparentSidenav, whiteSidenav, miniSidenav, darkMode }}
    >
      <MDBox pt={3} pb={1} px={4} textAlign="center">
        <MDBox
          display={{ xs: "block", xl: "none" }}
          position="absolute"
          top={0}
          right={0}
          p={1.625}
          onClick={closeSidenav}
          sx={{ cursor: "pointer" }}
        >
          <MDTypography variant="h6" color="secondary">
            <Icon sx={{ fontWeight: "bold" }}>close</Icon>
          </MDTypography>
        </MDBox>
        <MDBox component={NavLink} to="/dashboard" display="flex" alignItems="center">
          {brand && <MDBox component="img" src={brand} alt="Brand" width="2rem" />}
          <MDBox
            width={!brandName && "100%"}
            sx={(theme) => sidenavLogoLabel(theme, { miniSidenav })}
          >
            <MDTypography component="h6" variant="button" fontWeight="medium" color={textColor}>
              {brandName}
            </MDTypography>
          </MDBox>
        </MDBox>
      </MDBox>
      <Divider
        light={
          (!darkMode && !whiteSidenav && !transparentSidenav) ||
          (darkMode && !transparentSidenav && whiteSidenav)
        }
      />
      <List sx={{ overflowY: "auto", flex: 1 }}>{renderSections}</List>
    </SidenavRoot>
  );
}

Sidenav.defaultProps = {
  color: "info",
  brand: "",
};

Sidenav.propTypes = {
  color: PropTypes.oneOf(["primary", "secondary", "info", "success", "warning", "error", "dark"]),
  brand: PropTypes.string,
  brandName: PropTypes.string.isRequired,
  routes: PropTypes.arrayOf(PropTypes.object).isRequired,
};

export default Sidenav;
