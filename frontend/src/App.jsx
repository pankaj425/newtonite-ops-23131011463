import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth.jsx";
import Layout from "./components/Layout.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import ItemDetail from "./pages/ItemDetail.jsx";
import ItemForm from "./pages/ItemForm.jsx";
import ItemsList from "./pages/ItemsList.jsx";
import Login from "./pages/Login.jsx";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="center muted">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="items" element={<ItemsList />} />
        <Route path="items/new" element={<ItemForm mode="create" />} />
        <Route path="items/:id" element={<ItemDetail />} />
        <Route path="items/:id/edit" element={<ItemForm mode="edit" />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
