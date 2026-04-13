/// <reference types="react-scripts" />

interface WindowEnv {
  REACT_APP_BACKEND_URL?: string;
}

interface Window {
  _env_?: WindowEnv;
}
