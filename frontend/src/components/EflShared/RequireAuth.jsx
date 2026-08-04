import PropTypes from "prop-types";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "context/AuthContext";

function RequireAuth({ children }) {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/authentication/sign-in" replace state={{ from: location }} />;
  }

  return children;
}

RequireAuth.propTypes = {
  children: PropTypes.node.isRequired,
};

export default RequireAuth;
