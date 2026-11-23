import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AdminLayout } from "@/components/layout/AdminLayout";
import DashboardPage from "@/pages/DashboardPage";
import DeliveriesPage from "@/pages/DeliveriesPage";
import DriverPage from "@/pages/DriverPage";
import RoutePage from "@/pages/RoutePage";
import { useAppStore } from "@/store/useAppStore";

export default function App() {
  const refresh = useAppStore((s) => s.refresh);

  // Ao abrir o app, busca os dados uma vez.
  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <BrowserRouter>
      <Routes>
        {/* Telas do lojista: compartilham a sidebar (AdminLayout) */}
        <Route element={<AdminLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="entregas" element={<DeliveriesPage />} />
          <Route path="rota" element={<RoutePage />} />
        </Route>
        {/* Tela do entregador: layout próprio, sem sidebar */}
        <Route path="/entregador" element={<DriverPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}