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

/** Dark sidebar = default dark gradient / darkMode sidenav (not white or light-transparent). */
function isDarkSidenav({ transparentSidenav, whiteSidenav, darkMode }) {
  if (whiteSidenav) return false;
  if (transparentSidenav && !darkMode) return false;
  return true;
}

function collapseItem(theme, ownerState) {
  const { palette, transitions, breakpoints, boxShadows, borders, functions } = theme;
  const { active, transparentSidenav, whiteSidenav, darkMode, sidenavColor } = ownerState;

  const { white, transparent, dark, grey, gradients } = palette;
  const { md } = boxShadows;
  const { borderRadius } = borders;
  const { pxToRem, rgba, linearGradient } = functions;
  const darkSidenav = isDarkSidenav({ transparentSidenav, whiteSidenav, darkMode });

  return {
    background: active
      ? linearGradient(gradients[sidenavColor].main, gradients[sidenavColor].state)
      : transparent.main,
    // Dark sidebar: always white text; light sidebar: dark text (white when active)
    color: darkSidenav || active ? white.main : dark.main,
    display: "flex",
    alignItems: "center",
    width: "100%",
    padding: `${pxToRem(8)} ${pxToRem(10)}`,
    margin: `${pxToRem(1.5)} ${pxToRem(16)}`,
    borderRadius: borderRadius.md,
    cursor: "pointer",
    userSelect: "none",
    whiteSpace: "nowrap",
    boxShadow: active && !whiteSidenav && !darkMode && !transparentSidenav ? md : "none",
    [breakpoints.up("xl")]: {
      transition: transitions.create(["box-shadow", "background-color"], {
        easing: transitions.easing.easeInOut,
        duration: transitions.duration.shorter,
      }),
    },

    "&:hover, &:focus": {
      backgroundColor: () => {
        let backgroundValue;

        if (!active) {
          backgroundValue = darkSidenav
            ? rgba(white.main, 0.2)
            : transparentSidenav && !darkMode
            ? grey[300]
            : rgba(whiteSidenav ? grey[400] : white.main, 0.2);
        }

        return backgroundValue;
      },
    },
  };
}

function collapseIconBox(theme, ownerState) {
  const { palette, transitions, borders, functions } = theme;
  const { transparentSidenav, whiteSidenav, darkMode, active } = ownerState;

  const { white, dark } = palette;
  const { borderRadius } = borders;
  const { pxToRem } = functions;
  const darkSidenav = isDarkSidenav({ transparentSidenav, whiteSidenav, darkMode });
  const iconColor = darkSidenav || active ? white.main : dark.main;

  return {
    minWidth: pxToRem(32),
    minHeight: pxToRem(32),
    color: iconColor,
    borderRadius: borderRadius.md,
    display: "grid",
    placeItems: "center",
    transition: transitions.create("margin", {
      easing: transitions.easing.easeInOut,
      duration: transitions.duration.standard,
    }),

    "& svg, svg g, & .MuiSvgIcon-root": {
      color: `${iconColor} !important`,
      fill: iconColor,
    },
  };
}

const collapseIcon = ({ palette: { white, dark } }, { active, darkSidenav }) => ({
  color: active || darkSidenav ? white.main : dark.main,
});

function collapseText(theme, ownerState) {
  const { typography, transitions, breakpoints, functions, palette } = theme;
  const { miniSidenav, transparentSidenav, whiteSidenav, darkMode, active } = ownerState;

  const { size, fontWeightRegular, fontWeightLight } = typography;
  const { pxToRem } = functions;
  const { white, dark } = palette;
  const darkSidenav = isDarkSidenav({ transparentSidenav, whiteSidenav, darkMode });
  const textColor = darkSidenav || active ? white.main : dark.main;

  return {
    marginLeft: pxToRem(10),
    color: textColor,

    [breakpoints.up("xl")]: {
      opacity: miniSidenav || (miniSidenav && transparentSidenav) ? 0 : 1,
      maxWidth: miniSidenav || (miniSidenav && transparentSidenav) ? 0 : "100%",
      marginLeft: miniSidenav || (miniSidenav && transparentSidenav) ? 0 : pxToRem(10),
      transition: transitions.create(["opacity", "margin"], {
        easing: transitions.easing.easeInOut,
        duration: transitions.duration.standard,
      }),
    },

    "& span": {
      color: `${textColor} !important`,
      fontWeight: active ? fontWeightRegular : fontWeightLight,
      fontSize: size.sm,
      lineHeight: 0,
    },
  };
}

export { collapseItem, collapseIconBox, collapseIcon, collapseText, isDarkSidenav };
