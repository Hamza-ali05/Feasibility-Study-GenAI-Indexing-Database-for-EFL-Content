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

import { forwardRef } from "react";

import PropTypes from "prop-types";

import MDInputRoot from "components/MDInput/MDInputRoot";

const MDInput = forwardRef(({ error, success, disabled, ...rest }, ref) => (
  <MDInputRoot {...rest} ref={ref} ownerState={{ error, success, disabled }} />
));

MDInput.defaultProps = {
  error: false,
  success: false,
  disabled: false,
};

MDInput.propTypes = {
  error: PropTypes.bool,
  success: PropTypes.bool,
  disabled: PropTypes.bool,
};

export default MDInput;
