import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NewDelivery } from "@/types/domain";
import { deliveriesService } from "@/services/deliveriesService";
import { useAppStore } from "@/store/useAppStore";

const hookHarness = {
  slot: 0,
  states: [] as unknown[],
  reset() {
    this.slot = 0;
    this.states = [];
  },
  beginRender() {
    this.slot = 0;
  },
};

const captured = {
  openFormClick: null as (() => void) | null,
  pageOnSubmit: null as ((values: NewDelivery) => Promise<void>) | null,
};

vi.mock("react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react")>();
  return {
    ...actual,
    useState: (initial: unknown) => {
      const idx = hookHarness.slot++;
      if (!(idx in hookHarness.states)) {
        hookHarness.states[idx] = initial;
      }
      const setState = (updater: unknown) => {
        hookHarness.states[idx] =
          typeof updater === "function"
            ? (updater as (prev: unknown) => unknown)(hookHarness.states[idx])
            : updater;
      };
      return [hookHarness.states[idx], setState];
    },
  };
});

vi.mock("@/components/ui/Button", () => ({
  Button: (props: { onClick?: () => void; children?: unknown }) => {
    if (typeof props.onClick === "function" && Array.isArray(props.children)) {
      if (props.children.includes("Nova entrega")) {
        captured.openFormClick = props.onClick;
      }
    }
    return null;
  },
}));

vi.mock("@/components/shared/DeliveryForm", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/components/shared/DeliveryForm")>();
  return {
    DeliveryForm: (props: {
      onSubmit: (values: NewDelivery) => Promise<void>;
      onCancel: () => void;
      submitting?: boolean;
    }) => {
      captured.pageOnSubmit = props.onSubmit;
      return actual.DeliveryForm(props);
    },
  };
});

import { DeliveryForm } from "@/components/shared/DeliveryForm";
import DeliveriesPage from "./DeliveriesPage";

describe("DeliveriesPage + DeliveryForm — preservação de dados em erro", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    hookHarness.reset();
    captured.openFormClick = null;
    captured.pageOnSubmit = null;

    useAppStore.setState({
      deliveries: [],
      route: null,
      initialized: true,
      loading: false,
      error: null,
      nowSimulated: "19:45",
    });
  });

  it("propaga rejeição de addDelivery em DeliveriesPage e preserva os valores digitados em DeliveryForm", async () => {
    const createSpy = vi
      .spyOn(deliveriesService, "create")
      .mockRejectedValue(new Error("Falha ao cadastrar entrega"));

    const pageStates: unknown[] = [];
    const renderPage = () => {
      hookHarness.states = pageStates;
      hookHarness.beginRender();
      return renderToStaticMarkup(<DeliveriesPage />);
    };

    // 1. Renderiza DeliveriesPage e aciona "Nova entrega" para abrir o painel
    renderPage();
    expect(captured.openFormClick).not.toBeNull();
    captured.openFormClick!();

    const htmlWithForm = renderPage();
    expect(htmlWithForm).toContain("Cadastrar nova entrega");
    expect(captured.pageOnSubmit).not.toBeNull();

    // 2. Renderiza DeliveryForm conectado ao handleCreate real de DeliveriesPage
    const formStates: unknown[] = [];
    const renderForm = () => {
      hookHarness.states = formStates;
      hookHarness.beginRender();
      return renderToStaticMarkup(
        <DeliveryForm onSubmit={captured.pageOnSubmit!} onCancel={() => {}} />,
      );
    };

    renderForm();
    formStates[0] = {
      ...(formStates[0] as NewDelivery),
      customerName: "Mariana Costa",
      address: "Rua das Flores, 250",
    };

    // 3. Executa o fluxo de submit com handleCreate real de DeliveriesPage
    await expect(captured.pageOnSubmit!(formStates[0] as NewDelivery)).rejects.toThrow(
      "Falha ao cadastrar entrega",
    );
    expect(createSpy).toHaveBeenCalledTimes(1);

    // 4. Confirma que os valores preenchidos continuam no formulário e o painel permanece aberto
    const htmlAfterError = renderForm();
    expect(htmlAfterError).toContain('value="Mariana Costa"');
    expect(htmlAfterError).toContain('value="Rua das Flores, 250"');
    expect(renderPage()).toContain("Cadastrar nova entrega");
  });
});