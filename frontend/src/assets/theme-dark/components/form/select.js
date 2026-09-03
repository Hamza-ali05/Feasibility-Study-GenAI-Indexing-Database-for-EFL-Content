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

import colors from "assets/theme-dark/base/colors";

import pxToRem from "assets/theme-dark/functions/pxToRem";

const { transparent } = colors;

const select = {
  defaultProps: {
    MenuProps: {
      PaperProps: {
        sx: {
          minWidth: pxToRem(280),
          maxHeight: 320,
        },
      },
      anchorOrigin: { vertical: "bottom", horizontal: "left" },
      transformOrigin: { vertical: "top", horizontal: "left" },
    },
  },
  styleOverrides: {
    root: {
      minWidth: pxToRem(260),
    },

    select: {
      display: "flex",
      alignItems: "center",
      minHeight: pxToRem(44),
      minWidth: pxToRem(240),
      padding: `${pxToRem(10)} ${pxToRem(40)} ${pxToRem(10)} ${pxToRem(16)} !important`,
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap",

      "& .Mui-selected": {
        backgroundColor: transparent.main,
      },
    },

    selectMenu: {
      background: "none",
      height: "none",
      minHeight: "none",
      overflow: "unset",
    },

    icon: {
      display: "inline-flex",
      right: pxToRem(12),
      fontSize: pxToRem(22),
    },
  },
};

export default select;
