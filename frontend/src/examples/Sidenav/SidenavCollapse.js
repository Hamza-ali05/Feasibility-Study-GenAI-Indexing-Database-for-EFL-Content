/**
=========================================================
* EFL IndexDB - v2.2.0
=========================================================

* Product Page: https://www.creative-tim.com/product/material-dashboard-react
* Copyright 2023 Creative Tim (https://www.creative-tim.com)

Coded by www.creative-tim.com

 =========================================================

* The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
*/

import PropTypes from "prop-types";
import { cloneElement, isValidElement } from "react";

import ListItem from "@mui/material/ListItem";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Icon from "@mui/material/Icon";
import ExpandLess from "@mui/icons-material/ExpandLess";
import ExpandMore from "@mui/icons-material/ExpandMore";

import MDBox from "components/MDBox";

import {
  collapseItem,
  collapseIconBox,
  collapseIcon,
  collapseText,
  isDarkSidenav,
} from "examples/Sidenav/styles/sidenavCollapse";

import { useMaterialUIController } from "context";

function SidenavCollapse({ icon, name, active, collapsible, open, onClick, ...rest }) {
  const [controller] = useMaterialUIController();
  const { miniSidenav, transparentSidenav, whiteSidenav, darkMode, sidenavColor } = controller;
  const darkSidenav = isDarkSidenav({ transparentSidenav, whiteSidenav, darkMode });
  // Dark sidebar: always white labels / icons / chevrons
  const forceWhite = darkSidenav || active;
  const fg = forceWhite ? "#ffffff" : undefined;

  const renderedIcon =
    typeof icon === "string" ? (
      <Icon sx={(theme) => collapseIcon(theme, { active, darkSidenav })}>{icon}</Icon>
    ) : isValidElement(icon) ? (
      cloneElement(icon, {
        sx: [
          icon.props?.sx,
          fg && {
            color: `${fg} !important`,
            fill: `${fg} !important`,
          },
        ],
      })
    ) : (
      icon
    );

  return (
    <ListItem component="li" disablePadding sx={{ display: "block" }}>
      <MDBox
        {...rest}
        onClick={onClick}
        role={collapsible || onClick ? "button" : undefined}
        tabIndex={collapsible || onClick ? 0 : undefined}
        onKeyDown={
          collapsible || onClick
            ? (event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  if (typeof onClick === "function") onClick(event);
                }
              }
            : undefined
        }
        sx={[
          (theme) =>
            collapseItem(theme, {
              active,
              transparentSidenav,
              whiteSidenav,
              darkMode,
              sidenavColor,
            }),
          fg && {
            color: `${fg} !important`,
            "& .MuiTypography-root": { color: `${fg} !important` },
            "& .MuiSvgIcon-root": { color: `${fg} !important`, fill: `${fg} !important` },
          },
        ]}
      >
        <ListItemIcon
          sx={(theme) =>
            collapseIconBox(theme, { transparentSidenav, whiteSidenav, darkMode, active })
          }
        >
          {renderedIcon}
        </ListItemIcon>

        <MDBox display="flex" alignItems="center" sx={{ minWidth: 0, flex: "0 1 auto" }}>
          <ListItemText
            primary={name}
            sx={[
              (theme) =>
                collapseText(theme, {
                  miniSidenav,
                  transparentSidenav,
                  whiteSidenav,
                  darkMode,
                  active,
                }),
              {
                flex: "0 1 auto",
                margin: 0,
                "& .MuiTypography-root": {
                  whiteSpace: "nowrap",
                  ...(fg ? { color: `${fg} !important` } : {}),
                },
              },
            ]}
          />

          {collapsible && !miniSidenav && (
            <MDBox
              ml={0.5}
              display="flex"
              alignItems="center"
              sx={{
                opacity: 0.9,
                flexShrink: 0,
                color: fg || "inherit",
                "& .MuiSvgIcon-root": {
                  color: fg ? `${fg} !important` : "inherit",
                },
              }}
            >
              {open ? <ExpandLess fontSize="small" /> : <ExpandMore fontSize="small" />}
            </MDBox>
          )}
        </MDBox>
      </MDBox>
    </ListItem>
  );
}

SidenavCollapse.defaultProps = {
  active: false,
  collapsible: false,
  open: false,
  onClick: undefined,
};

SidenavCollapse.propTypes = {
  icon: PropTypes.node.isRequired,
  name: PropTypes.string.isRequired,
  active: PropTypes.bool,
  collapsible: PropTypes.bool,
  open: PropTypes.bool,
  onClick: PropTypes.func,
};

export default SidenavCollapse;
