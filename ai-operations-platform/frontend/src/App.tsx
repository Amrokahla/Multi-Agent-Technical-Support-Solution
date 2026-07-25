import { Routes, Route } from "react-router-dom";
import DashboardLayout from "./layouts/DashboardLayout";
import WorkforcePage from "./pages/WorkforcePage";

// Workforce Optimization is the first shipped feature; SLA Risk, Root Cause and
// Client Health mount here as they are built.
export default function App() {
  return (
    <Routes>
      <Route element={<DashboardLayout />}>
        <Route path="/" element={<WorkforcePage />} />
      </Route>
    </Routes>
  );
}
