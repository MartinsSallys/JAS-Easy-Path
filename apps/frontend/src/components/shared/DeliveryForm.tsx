import { useState, type ChangeEvent, type FormEvent } from "react";
import type { NewDelivery, Priority } from "@/types/domain";
import { USE_MOCK } from "@/services/config";
import { validateNewDelivery, type FieldErrors } from "@/utils/validation";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { inputClass } from "@/components/ui/fieldStyles";

interface DeliveryFormProps {
  onSubmit: (values: NewDelivery) => Promise<void>;
  onCancel: () => void;
  submitting?: boolean;
}

const EMPTY: NewDelivery = {
  orderCode: "",
  customerName: "",
  phone: "",
  address: "",
  windowStart: "",
  windowEnd: "",
  priority: "normal",
  notes: "",
};

type Control = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;

export function DeliveryForm({ onSubmit, onCancel, submitting }: DeliveryFormProps) {
  const [values, setValues] = useState<NewDelivery>(EMPTY);
  const [errors, setErrors] = useState<FieldErrors>({});

  const change = (field: keyof NewDelivery) => (event: ChangeEvent<Control>) => {
    setValues((current) => ({ ...current, [field]: event.target.value }));
  };

  const a11y = (field: keyof NewDelivery) => ({
    "aria-invalid": errors[field] ? true : undefined,
    "aria-describedby": errors[field] ? `${field}-error` : undefined,
  });

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const found = validateNewDelivery(values);
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    try {
      await onSubmit(values);
      setValues(EMPTY);
    } catch {
      // Erro exibido pelo banner global do store; valores digitados permanecem intactos
    }
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Cadastrar nova entrega</h2>
        <span className="text-xs text-slate-500">* Campos obrigatórios</span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Field id="orderCode" label="Código do pedido" error={errors.orderCode}>
          <input
            id="orderCode"
            placeholder="Ex.: #2005 (opcional)"
            className={inputClass(!!errors.orderCode)}
            value={values.orderCode}
            onChange={change("orderCode")}
            {...a11y("orderCode")}
          />
        </Field>

        <Field id="customerName" label="Cliente" required error={errors.customerName}>
          <input
            id="customerName"
            placeholder="Nome completo"
            className={inputClass(!!errors.customerName)}
            value={values.customerName}
            onChange={change("customerName")}
            {...a11y("customerName")}
          />
        </Field>

        <Field id="phone" label="Telefone" error={errors.phone}>
          <input
            id="phone"
            type="tel"
            placeholder="(71) 98888-1234"
            className={inputClass(!!errors.phone)}
            value={values.phone}
            onChange={change("phone")}
            {...a11y("phone")}
          />
        </Field>
      </div>

      <Field id="address" label="Endereço completo" required error={errors.address}>
        <input
          id="address"
          placeholder="Rua, número, bairro, cidade"
          className={inputClass(!!errors.address)}
          value={values.address}
          onChange={change("address")}
          {...a11y("address")}
        />
        {USE_MOCK ? (
          <p className="mt-1 text-xs text-slate-500">
            Modo demonstração: o ponto no mapa é gerado por simulação a partir do texto do endereço.
          </p>
        ) : null}
      </Field>

      <div className="grid gap-4 sm:grid-cols-3">
        <Field id="windowStart" label="Janela — Início (opcional)" error={errors.windowStart}>
          <input
            id="windowStart"
            placeholder="HH:mm (ex.: 09:00)"
            className={inputClass(!!errors.windowStart)}
            value={values.windowStart}
            onChange={change("windowStart")}
            {...a11y("windowStart")}
          />
        </Field>

        <Field id="windowEnd" label="Janela — Fim (opcional)" error={errors.windowEnd}>
          <input
            id="windowEnd"
            placeholder="HH:mm (ex.: 17:00)"
            className={inputClass(!!errors.windowEnd)}
            value={values.windowEnd}
            onChange={change("windowEnd")}
            {...a11y("windowEnd")}
          />
        </Field>

        <Field id="priority" label="Prioridade" error={errors.priority}>
          <select
            id="priority"
            className={inputClass(!!errors.priority)}
            value={values.priority}
            onChange={(e) =>
              setValues((cur) => ({ ...cur, priority: e.target.value as Priority }))
            }
          >
            <option value="low">Baixa</option>
            <option value="normal">Normal</option>
            <option value="high">Alta</option>
          </select>
        </Field>
      </div>

      <p className="text-xs text-slate-500">
        Deixe início e fim da janela em branco para usar o expediente padrão de 08:00 às 18:00 (mínimo de 8 min quando preenchida).
      </p>

      <Field id="notes" label="Observações" error={errors.notes}>
        <textarea
          id="notes"
          rows={2}
          placeholder="Ponto de referência, interfone, portão..."
          className={inputClass(!!errors.notes)}
          value={values.notes}
          onChange={change("notes")}
        />
      </Field>

      <div className="flex flex-wrap justify-end gap-2 pt-2">
        <Button variant="secondary" onClick={onCancel}>
          Cancelar
        </Button>
        <Button type="submit" disabled={submitting}>
          {submitting ? "Salvando..." : "Salvar entrega"}
        </Button>
      </div>
    </form>
  );
}