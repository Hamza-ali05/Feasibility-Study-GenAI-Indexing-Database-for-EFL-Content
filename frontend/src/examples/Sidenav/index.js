

import { useEffect, useState } from "react";

import { useLocation, NavLink } from "react-router-dom";

import PropTypes from "prop-types";

import List from "@mui/material/List";
import Divider from "@mui/material/Divider";
import Link from "@mui/material/Link";
import Icon from "@mui/material/Icon";
import MuiCollapse from "@mui/material/Collapse";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDButton from "components/MDButton";

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

function Sidenav({ color, brand, brandName, routes, ...rest }) {
  const [controller, dispatch] = useMaterialUIController();
  const { miniSidenav, transparentSidenav, whiteSidenav, darkMode, sidenavColor } = controller;
  const location = useLocation();
  const { pathname } = location;

  const [openNested, setOpenNested] = useState({});

  let textColor = "white";

  if (transparentSidenav || (whiteSidenav && !darkMode)) {
    textColor = "dark";
  } else if (whiteSidenav && darkMode) {
    textColor = "inherit";
  }

  const closeSidenav = () => setMiniSidenav(dispatch, true);

  const toggleNested = (key) => {
    setOpenNested((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  useEffect(() => {
    routes.forEach((r) => {
      if (r.type === "collapse" && Array.isArray(r.collapse)) {
        const childActive = r.collapse.some((c) => pathMatches(pathname, c.route));
        if (childActive) {
          setOpenNested((prev) => (prev[r.key] ? prev : { ...prev, [r.key]: true }));
        }
      }
    });
  }, [pathname, routes]);

  useEffect(() => {
    function handleMiniSidenav() {
      setMiniSidenav(dispatch, window.innerWidth < 1200);
      setTransparentSidenav(dispatch, window.innerWidth < 1200 ? false : transparentSidenav);
      setWhiteSidenav(dispatch, window.innerWidth < 1200 ? false : whiteSidenav);
    }

    window.addEventListener("resize", handleMiniSidenav);
    handleMiniSidenav();
    return () => window.removeEventListener("resize", handleMiniSidenav);
  }, [dispatch, location]);

  const renderRoutes = routes.map(
    ({ type, name, icon, title, noCollapse, key, href, route, collapse }) => {
      let returnValue;

      if (type === "collapse") {

        if (Array.isArray(collapse) && collapse.length > 0) {
          const isOpen = Boolean(openNested[key]);
          const childActive = collapse.some((c) => pathMatches(pathname, c.route));

          returnValue = (
            <MDBox key={key}>
              <MDBox onClick={() => toggleNested(key)} sx={{ cursor: "pointer" }}>
                <SidenavCollapse
                  name={name}
                  icon={icon}
                  active={childActive}
                  open={isOpen}
                  collapsible
                />
              </MDBox>
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
                    <NavLink key={child.key} to={child.route}>
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
        } else if (href) {
          returnValue = (
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
        } else {
          returnValue = (
            <NavLink key={key} to={route}>
              <SidenavCollapse name={name} icon={icon} active={pathMatches(pathname, route)} />
            </NavLink>
          );
        }
      } else if (type === "title") {
        returnValue = (
          <MDTypography
            key={key}
            color={textColor}
            display="block"
            variant="caption"
            fontWeight="bold"
            textTransform="uppercase"
            pl={3}
            mt={2}
            mb={1}
            ml={1}
          >
            {title}
          </MDTypography>
        );
      } else if (type === "divider") {
        returnValue = (
          <Divider
            key={key}
            light={
              (!darkMode && !whiteSidenav && !transparentSidenav) ||
              (darkMode && !transparentSidenav && whiteSidenav)
            }
          />
        );
      } else {

        returnValue = null;
      }

      return returnValue;
    }
  );

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
        <MDBox component={NavLink} to="/" display="flex" alignItems="center">
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
      <List>{renderRoutes}</List>
      <MDBox p={2} mt="auto">
        <MDButton
          component="a"
          href="https://www.creative-tim.com/product/material-dashboard-pro-react"
          target="_blank"
          rel="noreferrer"
          variant="gradient"
          color={sidenavColor}
          fullWidth
        >
          upgrade to pro
        </MDButton>
      </MDBox>
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
