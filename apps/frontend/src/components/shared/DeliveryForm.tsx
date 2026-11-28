import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { Check, Loader2, MapPin, X } from "lucide-react";
import type { NewDelivery, Priority } from "@/types/domain";
import {
  searchAddressSuggestions,
  type AddressSuggestion,
} from "@/services/addressSuggestions";
import { USE_MOCK } from "@/services/config";
import {
  formatBrPhone,
  isValidOptionalPhone,
  validateNewDelivery,
  type FieldErrors,
} from "@/utils/validation";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { inputClass } from "@/components/ui/fieldStyles";

interface DeliveryFormProps {
  onSubmit: (values: NewDelivery) => Promise<void>;
  onCancel: () => void;
  submitting?: boolean;
  /** Quando informado, o formulário abre preenchido para editar a entrega. */
  initialValues?: NewDelivery;
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
type TouchedFields = Partial<Record<keyof NewDelivery, boolean>>;

function ValidationAdornment({ state }: { state: "valid" | "invalid" | "neutral" }) {
  if (state === "neutral") return null;
  if (state === "valid") {
    return (
      <span
        aria-label="Campo válido"
        className="pointer-events-none absolute top-1/2 right-3 inline-flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded-full bg-emerald-100 text-emerald-700"
      >
        <Check className="h-3.5 w-3.5 stroke-[2.5]" />
      </span>
    );
  }
  return (
    <span
      aria-label="Campo inválido"
      className="pointer-events-none absolute top-1/2 right-3 inline-flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded-full bg-red-100 text-red-600"
    >
      <X className="h-3.5 w-3.5 stroke-[2.5]" />
    </span>
  );
}

export function DeliveryForm({ onSubmit, onCancel, submitting, initialValues }: DeliveryFormProps) {
  const editing = initialValues !== undefined;
  const [values, setValues] = useState<NewDelivery>(initialValues ?? EMPTY);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [touched, setTouched] = useState<TouchedFields>({});

  // Estado do autocomplete de endereço
  const [suggestions, setSuggestions] = useState<AddressSuggestion[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [addressConfirmed, setAddressConfirmed] = useState(editing);
  const skipNextAutocompleteRef = useRef(editing);

  const syncFieldValidation = (nextValues: NewDelivery, field: keyof NewDelivery) => {
    const allErrors = validateNewDelivery(nextValues);
    setErrors((prev) => {
      const updated = { ...prev };
      if (allErrors[field]) {
        updated[field] = allErrors[field];
      } else {
        delete updated[field];
      }
      if (field === "windowStart" || field === "windowEnd") {
        if (allErrors.windowStart) updated.windowStart = allErrors.windowStart;
        else delete updated.windowStart;
        if (allErrors.windowEnd) updated.windowEnd = allErrors.windowEnd;
        else delete updated.windowEnd;
      }
      return updated;
    });
  };

  const change = (field: keyof NewDelivery) => (event: ChangeEvent<Control>) => {
    const rawValue = event.target.value;
    const nextValue = field === "phone" ? formatBrPhone(rawValue) : rawValue;
    const nextValues = { ...values, [field]: nextValue };

    setValues(nextValues);
    setTouched((prev) => ({ ...prev, [field]: true }));

    if (field === "address") {
      setAddressConfirmed(false);
      if (nextValue.trim().length < 4) {
        setSuggestions([]);
        setShowSuggestions(false);
        setLoadingSuggestions(false);
      }
    }

    syncFieldValidation(nextValues, field);
  };

  const markTouched = (field: keyof NewDelivery) => () => {
    setTouched((prev) => ({ ...prev, [field]: true }));
    syncFieldValidation(values, field);
  };

  useEffect(() => {
    if (skipNextAutocompleteRef.current) {
      skipNextAutocompleteRef.current = false;
      return;
    }

    const query = values.address.trim();
    if (query.length < 4) return;

    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoadingSuggestions(true);
      try {
        const results = await searchAddressSuggestions(query, controller.signal);
        if (!controller.signal.aborted) {
          setSuggestions(results);
          setShowSuggestions(results.length > 0);
        }
      } catch {
        if (!controller.signal.aborted) {
          setSuggestions([]);
          setShowSuggestions(false);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoadingSuggestions(false);
        }
      }
    }, 450);

    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [values.address]);

  const handleSelectSuggestion = (item: AddressSuggestion) => {
    skipNextAutocompleteRef.current = true;
    const nextValues = { ...values, address: item.label };
    setValues(nextValues);
    setTouched((prev) => ({ ...prev, address: true }));
    setAddressConfirmed(true);
    setSuggestions([]);
    setShowSuggestions(false);
    syncFieldValidation(nextValues, "address");
  };

  const a11y = (field: keyof NewDelivery) => ({
    "aria-invalid": errors[field] ? true : undefined,
    "aria-describedby": errors[field] ? `${field}-error` : undefined,
  });

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const found = validateNewDelivery(values);
    setErrors(found);
    setTouched({
      customerName: true,
      phone: Boolean(values.phone.trim()),
      address: true,
      windowStart: Boolean(values.windowStart.trim()),
      windowEnd: Boolean(values.windowEnd.trim()),
    });
    if (Object.keys(found).length > 0) return;

    try {
      await onSubmit(values);
      setValues(EMPTY);
      setTouched({});
      setAddressConfirmed(false);
    } catch {
      // Erro exibido pelo banner global do store; valores digitados permanecem intactos
    }
  };

  const customerState = errors.customerName
    ? "invalid"
    : touched.customerName && values.customerName.trim().length >= 2
      ? "valid"
      : "neutral";

  const phoneDigits = values.phone.replace(/\D/g, "");
  const phoneState =
    phoneDigits.length === 0
      ? "neutral"
      : isValidOptionalPhone(values.phone)
        ? "valid"
        : "invalid";

  const addressState = errors.address
    ? "invalid"
    : addressConfirmed || (touched.address && values.address.trim().length >= 6)
      ? "valid"
      : "neutral";

  const windowStartState = errors.windowStart
    ? "invalid"
    : touched.windowStart && values.windowStart.trim().length >= 4
      ? "valid"
      : "neutral";

  const windowEndState = errors.windowEnd
    ? "invalid"
    : touched.windowEnd && values.windowEnd.trim().length >= 4
      ? "valid"
      : "neutral";

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold text-slate-900">
          {editing ? "Editar entrega" : "Cadastrar nova entrega"}
        </h2>
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
          <div className="relative">
            <input
              id="customerName"
              placeholder="Nome completo"
              className={`${inputClass(!!errors.customerName)} pr-10 ${
                customerState === "valid" ? "border-emerald-500 focus:border-emerald-600" : ""
              }`}
              value={values.customerName}
              onChange={change("customerName")}
              onBlur={markTouched("customerName")}
              {...a11y("customerName")}
            />
            <ValidationAdornment state={customerState} />
          </div>
        </Field>

        <Field id="phone" label="Telefone" error={errors.phone}>
          <div className="relative">
            <input
              id="phone"
              type="tel"
              inputMode="tel"
              placeholder="(71) 98888-1234"
              className={`${inputClass(!!errors.phone)} pr-10 ${
                phoneState === "valid" ? "border-emerald-500 focus:border-emerald-600" : ""
              }`}
              value={values.phone}
              onChange={change("phone")}
              onBlur={markTouched("phone")}
              {...a11y("phone")}
            />
            <ValidationAdornment state={phoneState} />
          </div>
        </Field>
      </div>

      <Field id="address" label="Endereço completo" required error={errors.address}>
        <div className="relative">
          <input
            id="address"
            autoComplete="off"
            placeholder="Digite rua, número, bairro ou cidade para ver sugestões..."
            className={`${inputClass(!!errors.address)} pr-10 ${
              addressState === "valid" ? "border-emerald-500 focus:border-emerald-600" : ""
            }`}
            value={values.address}
            onChange={change("address")}
            onFocus={() => {
              if (suggestions.length > 0) setShowSuggestions(true);
            }}
            onBlur={() => {
              markTouched("address")();
              window.setTimeout(() => setShowSuggestions(false), 180);
            }}
            {...a11y("address")}
          />

          {loadingSuggestions ? (
            <Loader2
              aria-label="Buscando sugestões de endereço"
              className="pointer-events-none absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 animate-spin text-blue-600"
            />
          ) : (
            <ValidationAdornment state={addressState} />
          )}

          {showSuggestions && suggestions.length > 0 ? (
            <ul
              role="listbox"
              aria-label="Sugestões de endereço"
              className="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-xl border border-slate-200 bg-white py-1 shadow-lg"
            >
              {suggestions.map((item, idx) => (
                <li key={`${item.label}-${idx}`}>
                  <button
                    type="button"
                    onMouseDown={(e) => {
                      e.preventDefault();
                      handleSelectSuggestion(item);
                    }}
                    className="flex w-full items-start gap-2.5 px-3 py-2 text-left text-xs text-slate-700 hover:bg-blue-50 hover:text-blue-900"
                  >
                    <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-blue-600" />
                    <span className="leading-snug">{item.label}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>

        {addressConfirmed ? (
          <p className="mt-1 text-xs font-medium text-emerald-700">
            Endereço confirmado pelas sugestões.
          </p>
        ) : USE_MOCK ? (
          <p className="mt-1 text-xs text-slate-500">
            Modo demonstração: digite ao menos 4 letras para ver sugestões ou informe um endereço livre.
          </p>
        ) : null}
      </Field>

      <div className="grid gap-4 sm:grid-cols-3">
        <Field id="windowStart" label="Janela — Início (opcional)" error={errors.windowStart}>
          <div className="relative">
            <input
              id="windowStart"
              placeholder="HH:mm (ex.: 09:00)"
              className={`${inputClass(!!errors.windowStart)} pr-10 ${
                windowStartState === "valid" ? "border-emerald-500 focus:border-emerald-600" : ""
              }`}
              value={values.windowStart}
              onChange={change("windowStart")}
              onBlur={markTouched("windowStart")}
              {...a11y("windowStart")}
            />
            <ValidationAdornment state={windowStartState} />
          </div>
        </Field>

        <Field id="windowEnd" label="Janela — Fim (opcional)" error={errors.windowEnd}>
          <div className="relative">
            <input
              id="windowEnd"
              placeholder="HH:mm (ex.: 17:00)"
              className={`${inputClass(!!errors.windowEnd)} pr-10 ${
                windowEndState === "valid" ? "border-emerald-500 focus:border-emerald-600" : ""
              }`}
              value={values.windowEnd}
              onChange={change("windowEnd")}
              onBlur={markTouched("windowEnd")}
              {...a11y("windowEnd")}
            />
            <ValidationAdornment state={windowEndState} />
          </div>
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
        <Button variant="secondary" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
        <Button type="submit" disabled={submitting}>
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              {editing ? "Salvando alterações..." : "Salvando entrega..."}
            </>
          ) : editing ? (
            "Salvar alterações"
          ) : (
            "Salvar entrega"
          )}
        </Button>
      </div>
    </form>
  );
}