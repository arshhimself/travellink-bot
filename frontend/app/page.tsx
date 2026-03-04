"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Send, Plane, User, Loader2, X, Check,
  ChevronRight, AlertCircle, CheckCircle2, Info, MapPin,
  Luggage, Utensils, Shield, Dumbbell, Package, Coffee, Armchair,
  Plus, Minus
} from "lucide-react";
import axios from "axios";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ─── Types ───────────────────────────────────────────────────────────────────

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  flightResults?: FlightResponse | null;
  ancillaryResults?: AncillaryResponse | null;
}

interface FareDetail {
  tax: string;
  adultFare: string;
  childFare: string;
  infantFare: string;
}

interface FlightClass {
  flightid: number;
  freeseats: number;
  className: string;
  classCode: string;
  cabinClass: string;
  currency: string;
  baggageAllowance: number;
  baggageUnit: string;
  fare: FareDetail;
  fareid: number;
}

interface Flight {
  direction: string;
  flight_code: string;
  flight_number: string;
  flight_type?: string;
  origin?: string;
  destination?: string;
  origin_code?: string;
  destination_code?: string;
  departure_time: string;
  arrival_time: string;
  start_time?: string;
  end_time?: string;
  via?: string | null;
  price: string;
  tax: string;
  seats?: string;
  seats_available?: number;
  classes: Record<string, FlightClass>;
}

interface BookingContext {
  from_code: string;
  to_code: string;
  adults: number;
  child: number;
  infant: number;
  triptype: string;
  departure_date?: string;
  return_date?: string;
}

interface FlightResponse {
  type: "flight_results";
  header: string;
  sub_header: string;
  context: BookingContext;
  data: Flight[];
}

// ─── Ancillary Types ─────────────────────────────────────────────────────────

interface AncillaryItem {
  itemid: number | string;
  name: string;
  category: string;
  price: string;
  currency: string;
  description: string;
}

interface AncillaryResponse {
  type: "ancillary_results";
  available: boolean;
  available_count: number;
  items: AncillaryItem[];
  booking_id?: number;
  flight_id?: number;
}

type ToastType = "success" | "error" | "info";
interface Toast {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getDepTime(f: Flight) { return f.departure_time || f.start_time || ""; }
function getArrTime(f: Flight) { return f.arrival_time || f.end_time || ""; }
function getSeats(f: Flight) { return f.seats_available ?? f.seats ?? "?"; }
function getOriginLabel(f: Flight, ctx: BookingContext) {
  return f.origin || f.origin_code || ctx.from_code;
}
function getDestLabel(f: Flight, ctx: BookingContext) {
  return f.destination || f.destination_code || ctx.to_code;
}

// ─── Toast ────────────────────────────────────────────────────────────────────

function ToastContainer({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: string) => void }) {
  return (
    <div className="fixed top-5 right-5 z-[100] flex flex-col gap-2 pointer-events-none">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, x: 60, scale: 0.95 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 60, scale: 0.95 }}
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
            className={cn(
              "pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl border shadow-2xl min-w-[280px] max-w-[360px]",
              t.type === "success" && "bg-red-600 border-red-800 text-white",
              t.type === "error" && "bg-[#1a0000] border-red-900 text-red-200",
              t.type === "info" && "bg-zinc-900 border-zinc-700 text-zinc-100"
            )}
          >
            <div className="mt-0.5 flex-shrink-0">
              {t.type === "success" && <CheckCircle2 className="w-4 h-4" />}
              {t.type === "error" && <AlertCircle className="w-4 h-4" />}
              {t.type === "info" && <Info className="w-4 h-4" />}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-base font-bold uppercase tracking-wide">{t.title}</p>
              {t.message && <p className="text-sm opacity-75 mt-0.5">{t.message}</p>}
            </div>
            <button onClick={() => onDismiss(t.id)} className="opacity-60 hover:opacity-100 transition-opacity">
              <X className="w-3.5 h-3.5" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

// ─── Flight Card ──────────────────────────────────────────────────────────────

function FlightCard({ flight, context, onClick, disabled }: {
  flight: Flight; context: BookingContext; onClick: () => void; disabled?: boolean;
}) {
  const depTime = getDepTime(flight).slice(-5) || "--:--";
  const arrTime = getArrTime(flight).slice(-5) || "--:--";

  return (
    <motion.div
      whileHover={disabled ? {} : { scale: 1.01, y: -2 }}
      whileTap={disabled ? {} : { scale: 0.99 }}
      onClick={disabled ? undefined : onClick}
      className={cn("group relative overflow-hidden", disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer")}
    >
      {/* Red left accent bar */}
      <div className="absolute left-0 top-0 bottom-0 w-1 bg-red-600 group-hover:w-1.5 transition-all duration-200 rounded-l" />
      <div className="ml-1.5 bg-white border border-zinc-200 group-hover:border-red-600/40 rounded-r-2xl p-4 transition-all shadow-sm group-hover:shadow-md">

        {/* Top row */}
        <div className="flex items-center justify-between mb-3">
          <span className={cn(
            "text-[11px] font-black tracking-[0.15em] uppercase px-2 py-0.5 rounded-md",
            flight.direction === "Outbound" ? "bg-blue-100 text-blue-700" : "bg-emerald-100 text-emerald-700"
          )}>
            {flight.direction}
          </span>
          <div className="flex items-center gap-2">
            {flight.via && (
              <span className="text-[11px] bg-yellow-100 text-yellow-700 font-black px-2 py-0.5 rounded-md uppercase tracking-wider">
                Via {flight.via}
              </span>
            )}
            <span className="text-sm font-bold text-zinc-400 font-mono">{flight.flight_number || flight.flight_code}</span>
          </div>
        </div>

        {/* Route row */}
        <div className="flex items-center gap-4 mb-3">
          <div className="text-center min-w-[60px]">
            <div className="text-3xl font-black text-zinc-900 leading-none tracking-tight">{depTime}</div>
            <div className="text-xs font-black text-zinc-400 uppercase tracking-widest mt-1">{getOriginLabel(flight, context)}</div>
          </div>
          <div className="flex-1 flex flex-col items-center gap-1">
            <div className="w-full flex items-center gap-1.5">
              <div className="flex-1 h-px bg-zinc-200" />
              <div className="bg-red-600 p-1.5 rounded-full shadow-sm shadow-red-200">
                <Plane className="w-2.5 h-2.5 text-white rotate-90" />
              </div>
              <div className="flex-1 h-px bg-zinc-200" />
            </div>
            <div className="text-[10px] text-zinc-400 uppercase tracking-widest font-bold">{flight.flight_type || "Direct"}</div>
          </div>
          <div className="text-center min-w-[60px]">
            <div className="text-3xl font-black text-zinc-900 leading-none tracking-tight">{arrTime}</div>
            <div className="text-xs font-black text-zinc-400 uppercase tracking-widest mt-1">{getDestLabel(flight, context)}</div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between pt-3 border-t border-zinc-100">
          <div>
            <span className="text-2xl font-black text-red-600">${flight.price}</span>
            <span className="text-sm text-zinc-400 ml-1 font-medium">+ ${flight.tax} tax</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-zinc-400 font-medium">{getSeats(flight)} seats</span>
            <div className="flex items-center gap-1 bg-red-600 hover:bg-red-700 text-white text-sm font-black uppercase tracking-wider px-3 py-1.5 rounded-lg transition-colors">
              Select <ChevronRight className="w-3 h-3" />
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

// ─── Class Modal ──────────────────────────────────────────────────────────────

function ClassModal({ flight, context, submitting, selectedFareId, onClose, onSelect }: {
  flight: Flight; context: BookingContext; submitting: boolean;
  selectedFareId: number | null; onClose: () => void; onSelect: (cls: FlightClass) => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        initial={{ y: 80, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 80, opacity: 0 }}
        transition={{ type: "spring", stiffness: 380, damping: 32 }}
        onClick={(e) => e.stopPropagation()}
        className="w-full sm:max-w-lg bg-white rounded-t-3xl sm:rounded-3xl shadow-2xl overflow-hidden max-h-[90vh] flex flex-col"
      >
        {/* Red header */}
        <div className="bg-red-600 px-5 py-4 flex items-start justify-between">
          <div>
            <h3 className="text-lg font-black text-white uppercase tracking-wide">Choose Fare Class</h3>
            <p className="text-red-200 text-sm mt-0.5 font-bold">
              {getOriginLabel(flight, context)} → {getDestLabel(flight, context)} · {flight.flight_number || flight.flight_code}
            </p>
          </div>
          <button onClick={onClose} disabled={submitting}
            className="p-1.5 rounded-lg bg-red-700/50 hover:bg-red-700 text-white transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2.5 bg-zinc-50">
          {Object.entries(flight.classes).map(([code, cls]) => {
            const isSelected = selectedFareId === cls.fareid;
            const isLoading = submitting && isSelected;
            return (
              <motion.div key={code} whileTap={!submitting ? { scale: 0.99 } : {}}
                onClick={() => !submitting && onSelect(cls)}
                className={cn(
                  "relative p-4 rounded-2xl border-2 transition-all duration-200 cursor-pointer bg-white shadow-sm",
                  isSelected ? "border-red-600 shadow-md" :
                    submitting ? "opacity-40 cursor-not-allowed border-zinc-200" :
                      "border-zinc-200 hover:border-red-600/50 hover:shadow-md"
                )}
              >
                {isLoading && <div className="absolute inset-0 rounded-2xl bg-red-50 animate-pulse" />}
                <div className="relative flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <h4 className="font-black text-zinc-900 uppercase tracking-wide text-base">{cls.className}</h4>
                    {isSelected && !isLoading && <Check className="w-4 h-4 text-red-600" />}
                    {isLoading && <Loader2 className="w-4 h-4 text-red-600 animate-spin" />}
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-black text-red-600">${cls.fare.adultFare}</div>
                    <div className="text-xs text-zinc-400 font-bold">per adult</div>
                  </div>
                </div>
                <div className="relative grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs text-zinc-500 font-medium">
                  {[
                    `${cls.freeseats} seats left`,
                    `${cls.baggageAllowance}${cls.baggageUnit} baggage`,
                    cls.cabinClass,
                    `+$${cls.fare.tax} tax`,
                  ].map((item) => (
                    <div key={item} className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-red-600 flex-shrink-0" />
                      {item}
                    </div>
                  ))}
                </div>
              </motion.div>
            );
          })}
        </div>

        <div className="px-5 py-3 bg-white border-t border-zinc-100">
          <p className="text-center text-xs text-zinc-400 font-bold uppercase tracking-widest">
            Prices subject to availability · All fares in USD
          </p>
        </div>
      </motion.div>
    </motion.div>
  );
}

// ─── Ancillary Card ──────────────────────────────────────────────────────────

type LucideIcon = React.ComponentType<{ className?: string }>;

const CATEGORY_ICON_MAP: Record<string, LucideIcon> = {
  baggage: Luggage,
  meal: Utensils,
  seat: Armchair,
  lounge: Coffee,
  insurance: Shield,
  sport: Dumbbell,
  default: Package,
};

function getCategoryIcon(category: string): LucideIcon {
  const key = category.toLowerCase();
  for (const [k, v] of Object.entries(CATEGORY_ICON_MAP)) {
    if (key.includes(k)) return v;
  }
  return CATEGORY_ICON_MAP.default;
}

function AncillaryCard({ item, bookingId, flightId, paxNum, onAdded, onError }: {
  item: AncillaryItem;
  bookingId?: number;
  flightId?: number;
  paxNum: number;
  onAdded: (item: AncillaryItem) => void;
  onError: (msg: string) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState(false);

  const handleAdd = async () => {
    if (adding || added) return;
    setAdding(true);
    try {
      await axios.post("http://127.0.0.1:8000/add-ancillary", {
        booking_id: bookingId,
        flight_id: flightId,
        item_id: Number(item.itemid),
        pax_num: paxNum,
      });
      setAdded(true);
      onAdded(item);
    } catch (err: any) {
      onError(err?.response?.data?.detail || err?.message || "Failed to add extra");
    } finally {
      setAdding(false);
    }
  };

  const IconComponent = getCategoryIcon(item.category);

  return (
    <motion.div
      whileHover={!added ? { scale: 1.01, y: -1 } : {}}
      whileTap={!added ? { scale: 0.99 } : {}}
      className="group relative overflow-hidden"
    >
      <div className={cn(
        "absolute left-0 top-0 bottom-0 w-1 rounded-l transition-all duration-200",
        added ? "bg-red-600" : "bg-zinc-300 group-hover:w-1.5 group-hover:bg-red-600"
      )} />
      <div className={cn(
        "ml-1.5 bg-white border rounded-r-2xl p-3.5 transition-all shadow-sm",
        added ? "border-red-200" : "border-zinc-200 group-hover:border-red-200 group-hover:shadow-md"
      )}>
        <div className="flex items-center justify-between gap-3">
          {/* Icon + info */}
          <div className="flex items-center gap-3 min-w-0">
            <div className={cn(
              "w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0",
              added ? "bg-red-50" : "bg-zinc-100"
            )}>
              <IconComponent className={cn("w-5 h-5", added ? "text-red-600" : "text-zinc-500")} />
            </div>
            <div className="min-w-0">
              <div className="font-black text-zinc-900 text-sm uppercase tracking-wide leading-tight truncate">{item.name}</div>
              <div className={cn(
                "text-[10px] font-bold uppercase tracking-widest mt-0.5",
                added ? "text-red-600" : "text-zinc-400"
              )}>{item.category}</div>
              {item.description && item.description !== item.name && (
                <div className="text-[11px] text-zinc-400 mt-0.5 truncate">{item.description}</div>
              )}
            </div>
          </div>

          {/* Price + Toggle */}
          <div className="flex items-center gap-3 flex-shrink-0">
            <div className="text-right">
              <div className="text-xl font-black text-zinc-900">${item.price}</div>
              <div className="text-[10px] text-zinc-400 font-bold uppercase">{item.currency}</div>
            </div>
            <div className="flex flex-col items-center gap-1">
              <button
                onClick={handleAdd}
                disabled={adding}
                aria-pressed={added}
                className={cn(
                  "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border-2 transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-600 focus-visible:ring-offset-2",
                  added ? "bg-red-600 border-red-600" : "bg-zinc-200 border-zinc-300 hover:border-red-400",
                  adding && "opacity-60 cursor-wait"
                )}
              >
                <span className={cn(
                  "pointer-events-none inline-flex h-4 w-4 items-center justify-center rounded-full bg-white shadow-sm transition-transform duration-200",
                  added ? "translate-x-5" : "translate-x-0.5"
                )}>
                  {adding
                    ? <Loader2 className="w-2.5 h-2.5 text-red-600 animate-spin" />
                    : added
                      ? <Check className="w-2.5 h-2.5 text-red-600" />
                      : null}
                </span>
              </button>
              <span className={cn(
                "text-[9px] font-black uppercase tracking-wider",
                added ? "text-red-600" : "text-zinc-400"
              )}>
                {adding ? "Adding" : added ? "Added" : "Add"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

// ─── Weight Stepper ──────────────────────────────────────────────────────────

function isWeightGroup(category: string, items: AncillaryItem[]): boolean {
  if (category.toLowerCase().includes("weight") || category.toLowerCase().includes("excess")) return true;
  const kgPattern = /^\d+\s*kg/i;
  return items.filter((i) => kgPattern.test(i.name)).length > items.length / 2;
}

function WeightStepper({ items, bookingId, flightId, paxNum, onAdded, onError }: {
  items: AncillaryItem[];
  bookingId?: number;
  flightId?: number;
  paxNum: number;
  onAdded: (item: AncillaryItem) => void;
  onError: (msg: string) => void;
}) {
  const getKg = (name: string, desc = "") => {
    const m = (name + " " + desc).match(/(\d+)\s*kg/i);
    return m ? parseInt(m[1]) : 0;
  };
  // Only include items that have a real price, sorted ascending by kg
  const sorted = [...items]
    .filter(i => parseFloat(i.price) > 0)
    .sort((a, b) => getKg(a.name, a.description) - getKg(b.name, b.description));
  const maxKg = sorted.length ? getKg(sorted[sorted.length - 1].name, sorted[sorted.length - 1].description) : 0;
  const currency = sorted[0]?.currency ?? "USD";

  const [selectedIdx, setSelectedIdx] = useState(-1);
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState(false);

  const selectedItem = selectedIdx >= 0 ? sorted[selectedIdx] : null;
  const displayKg = selectedItem ? getKg(selectedItem.name, selectedItem.description) : 0;
  const totalPrice = selectedItem ? parseFloat(selectedItem.price) : 0;

  const handleAdd = async () => {
    if (!selectedItem || adding || added) return;
    setAdding(true);
    try {
      await axios.post("http://127.0.0.1:8000/add-ancillary", {
        booking_id: bookingId,
        flight_id: flightId,
        item_id: Number(selectedItem.itemid),
        pax_num: paxNum,
      });
      setAdded(true);
      onAdded(selectedItem);
    } catch (err: any) {
      onError(err?.response?.data?.detail || err?.message || "Failed to add baggage");
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="group relative overflow-hidden">
      <div className={cn(
        "absolute left-0 top-0 bottom-0 w-1 rounded-l transition-all duration-200",
        added ? "bg-red-600" : "bg-zinc-300 group-hover:bg-red-600"
      )} />
      <div className={cn(
        "ml-1.5 bg-white border rounded-r-2xl p-4 shadow-sm transition-all",
        added ? "border-red-200" : "border-zinc-200 group-hover:border-red-200"
      )}>
        {/* Title row */}
        <div className="flex items-center gap-2.5 mb-4">
          <div className={cn(
            "w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0",
            added ? "bg-red-50" : "bg-zinc-100"
          )}>
            <Luggage className={cn("w-4.5 h-4.5", added ? "text-red-600" : "text-zinc-500")} />
          </div>
          <div>
            <div className="font-black text-zinc-900 text-sm uppercase tracking-wide">Excess Baggage</div>
            <div className={cn("text-[10px] font-bold uppercase tracking-widest mt-0.5", added ? "text-red-600" : "text-zinc-400")}>
              {maxKg > 0 ? `Up to ${maxKg} kg available` : `${sorted.length} option${sorted.length !== 1 ? "s" : ""} available`}
            </div>
          </div>
        </div>

        {/* Stepper + price + toggle row */}
        <div className="flex items-center justify-between gap-4">
          {/* -/+ stepper */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSelectedIdx(i => Math.max(-1, i - 1))}
              disabled={selectedIdx === -1 || added}
              className="w-8 h-8 rounded-full border-2 border-zinc-200 flex items-center justify-center text-zinc-500 hover:border-red-600 hover:text-red-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <Minus className="w-3.5 h-3.5" />
            </button>
            <div className="min-w-[64px] text-center">
              <span className="text-2xl font-black text-zinc-900">{displayKg}</span>
              <span className="text-sm font-bold text-zinc-400 ml-1">KG</span>
            </div>
            <button
              onClick={() => setSelectedIdx(i => Math.min(sorted.length - 1, i + 1))}
              disabled={selectedIdx >= sorted.length - 1 || added}
              className="w-8 h-8 rounded-full border-2 border-zinc-200 flex items-center justify-center text-zinc-500 hover:border-red-600 hover:text-red-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Price + toggle */}
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className={cn("text-xl font-black", selectedItem ? "text-zinc-900" : "text-zinc-300")}>
                {selectedItem ? `$${totalPrice.toFixed(2)}` : "--"}
              </div>
              <div className="text-[10px] text-zinc-400 font-bold uppercase">{currency}</div>
            </div>
            <div className="flex flex-col items-center gap-1">
              <button
                onClick={handleAdd}
                disabled={!selectedItem || adding || added}
                aria-pressed={added}
                className={cn(
                  "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border-2 transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-600 focus-visible:ring-offset-2",
                  added ? "bg-red-600 border-red-600" :
                    selectedItem ? "bg-zinc-200 border-zinc-300 hover:border-red-400" :
                      "bg-zinc-100 border-zinc-200 opacity-40 cursor-not-allowed",
                  adding && "opacity-60 cursor-wait"
                )}
              >
                <span className={cn(
                  "pointer-events-none inline-flex h-4 w-4 items-center justify-center rounded-full bg-white shadow-sm transition-transform duration-200",
                  added ? "translate-x-5" : "translate-x-0.5"
                )}>
                  {adding
                    ? <Loader2 className="w-2.5 h-2.5 text-red-600 animate-spin" />
                    : added
                      ? <Check className="w-2.5 h-2.5 text-red-600" />
                      : null}
                </span>
              </button>
              <span className={cn(
                "text-[9px] font-black uppercase tracking-wider",
                added ? "text-red-600" : "text-zinc-400"
              )}>
                {adding ? "Adding" : added ? "Added" : "Add"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function AncillaryResults({ data, paxCount, onItemAdded, onError, onContinue }: {
  data: AncillaryResponse;
  paxCount: number;
  onItemAdded: (item: AncillaryItem) => void;
  onError: (msg: string) => void;
  onContinue: () => void;
}) {
  const [activePax, setActivePax] = useState(0);

  if (!data.available || !data.items?.length) return null;

  // Group by category
  const grouped: Record<string, AncillaryItem[]> = {};
  for (const item of data.items) {
    const cat = item.category || "Other";
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(item);
  }

  const totalPax = Math.max(paxCount, 1);

  return (
    <div className="p-4 space-y-4">
      {/* Header banner */}
      <div className="bg-red-600 rounded-xl px-4 py-3 flex items-center justify-between">
        <div>
          <div className="text-white font-black text-base uppercase tracking-wide">Extras & Add-ons</div>
          <div className="text-red-200 text-xs mt-0.5 font-bold">{data.available_count} option{data.available_count !== 1 ? "s" : ""} available</div>
        </div>
        <Luggage className="w-5 h-5 text-white/60" />
      </div>

      {/* Passenger tabs — only if more than 1 passenger */}
      {totalPax > 1 && (
        <div className="flex gap-1.5 bg-zinc-200 rounded-xl p-1">
          {Array.from({ length: totalPax }, (_, i) => (
            <button
              key={i}
              onClick={() => setActivePax(i)}
              className={cn(
                "flex-1 py-2 rounded-lg text-xs font-black uppercase tracking-wider transition-all",
                activePax === i
                  ? "bg-red-600 text-white shadow-md"
                  : "text-zinc-500 hover:text-zinc-700 hover:bg-zinc-100"
              )}
            >
              Passenger {i + 1}
            </button>
          ))}
        </div>
      )}

      {Object.entries(grouped).map(([category, items]) => (
        <div key={`${category}-${activePax}`} className="space-y-2">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-zinc-500 px-1">{category}</p>
          {isWeightGroup(category, items) ? (
            <WeightStepper
              key={`weight-${activePax}`}
              items={items}
              bookingId={data.booking_id}
              flightId={data.flight_id}
              paxNum={activePax}
              onAdded={onItemAdded}
              onError={onError}
            />
          ) : (
            items.map((item) => (
              <AncillaryCard
                key={`${item.itemid}-${activePax}`}
                item={item}
                bookingId={data.booking_id}
                flightId={data.flight_id}
                paxNum={activePax}
                onAdded={onItemAdded}
                onError={onError}
              />
            ))
          )}
        </div>
      ))}

      {/* Continue button */}
      <button
        onClick={onContinue}
        className="w-full py-3 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-white font-black text-sm uppercase tracking-wider transition-colors flex items-center justify-center gap-2 shadow-md"
      >
        Continue
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
}

// ─── Passenger Form ───────────────────────────────────────────────────────────

interface PassengerFormData {
  firstname: string;
  lastname: string;
  birthdate: string;
  phone: string;
  email: string;
}

function PassengerForm({ paxCount, bookingId, fromCode, toCode, onSuccess, onError }: {
  paxCount: number;
  bookingId: number;
  fromCode: string;
  toCode: string;
  onSuccess: (pnr: string) => void;
  onError: (msg: string) => void;
}) {
  const totalPax = Math.max(paxCount, 1);
  const [activePax, setActivePax] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [confirmData, setConfirmData] = useState<any>(null);
  const [passengers, setPassengers] = useState<PassengerFormData[]>(
    Array.from({ length: totalPax }, () => ({
      firstname: "", lastname: "", birthdate: "", phone: "", email: "",
    }))
  );

  const updateField = (idx: number, field: keyof PassengerFormData, value: string) => {
    setPassengers((prev) => {
      const updated = [...prev];
      updated[idx] = { ...updated[idx], [field]: value };
      return updated;
    });
  };

  const isComplete = passengers.every(
    (p) => p.firstname.trim() && p.lastname.trim() && p.birthdate.trim() && p.phone.trim() && p.email.trim()
  );

  const handleSubmit = async () => {
    if (!isComplete || submitting || submitted) return;
    setSubmitting(true);
    try {
      const res = await axios.post("http://127.0.0.1:8000/confirm-booking", {
        booking_id: bookingId,
        passengers: passengers.map((p) => ({
          firstname: p.firstname.trim(),
          lastname: p.lastname.trim(),
          birthdate: p.birthdate.trim(),
          phone: p.phone.trim(),
          email: p.email.trim(),
        })),
      });
      setSubmitted(true);
      const booking = res.data?.details?.aerocrs || {};
      setConfirmData(booking);
      const pnr = booking.pnrref || "Confirmed";
      onSuccess(pnr);
    } catch (err: any) {
      onError(err?.response?.data?.detail || err?.message || "Confirmation failed");
    } finally {
      setSubmitting(false);
    }
  };

  const pax = passengers[activePax];

  const inputCls = "w-full bg-zinc-100 border-2 border-zinc-200 focus:border-red-600 outline-none rounded-xl px-3 py-2.5 text-sm text-zinc-900 font-medium placeholder:text-zinc-400 transition-colors";
  const labelCls = "text-[10px] font-black uppercase tracking-widest text-zinc-500 mb-1 block";

  if (submitted && confirmData) {
    const pnr = confirmData.pnrref || "N/A";
    const total = confirmData.topay || "0.00";
    const currency = confirmData.currency || "USD";
    const link = confirmData.linktobooking;
    const paxList = confirmData.passenger || [];
    const status = confirmData.status || "OK";
    const ticketDeadline = confirmData.pnrttl;

    return (
      <div className="-mx-4 px-2 py-4">
        <motion.div
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-2xl shadow-xl overflow-hidden border border-zinc-200 max-w-[640px] mx-auto"
        >
          {/* Top strip */}
          <div className="bg-red-600 px-6 py-2 flex items-center justify-between">
            <span className="text-white/70 text-[10px] font-black uppercase tracking-[0.25em]">Boarding Pass</span>
            <span className={cn(
              "text-[10px] font-black uppercase tracking-wider px-2.5 py-0.5 rounded-full",
              status === "OK" ? "bg-white/20 text-white" : "bg-yellow-500/20 text-yellow-200"
            )}>{status === "OK" ? "✓ Confirmed" : status}</span>
          </div>

          {/* Main body — horizontal layout */}
          <div className="flex">
            {/* Left: Route section */}
            <div className="flex-1 px-6 py-5">
              <div className="flex items-center gap-5 mb-5">
                <div className="text-center">
                  <div className="text-4xl font-black text-zinc-900 tracking-tight leading-none">{fromCode}</div>
                  <div className="text-[9px] font-bold text-zinc-400 uppercase tracking-widest mt-1">Origin</div>
                </div>
                <div className="flex-1 flex items-center gap-2">
                  <div className="flex-1 h-[2px] bg-gradient-to-r from-red-600 to-red-300 rounded-full" />
                  <div className="bg-red-600 p-2 rounded-full shadow-md shadow-red-200">
                    <Plane className="w-4 h-4 text-white rotate-90" />
                  </div>
                  <div className="flex-1 h-[2px] bg-gradient-to-r from-red-300 to-red-600 rounded-full" />
                </div>
                <div className="text-center">
                  <div className="text-4xl font-black text-zinc-900 tracking-tight leading-none">{toCode}</div>
                  <div className="text-[9px] font-bold text-zinc-400 uppercase tracking-widest mt-1">Destination</div>
                </div>
              </div>

              {/* Info grid */}
              <div className="grid grid-cols-3 gap-x-4 gap-y-3">
                <div>
                  <div className="text-[9px] font-black uppercase tracking-widest text-zinc-400">PNR</div>
                  <div className="text-lg font-black text-zinc-900 tracking-wider">{pnr}</div>
                </div>
                <div>
                  <div className="text-[9px] font-black uppercase tracking-widest text-zinc-400">Booking</div>
                  <div className="text-lg font-black text-zinc-900 tracking-wider">{bookingId}</div>
                </div>
                <div>
                  <div className="text-[9px] font-black uppercase tracking-widest text-zinc-400">Total</div>
                  <div className="text-lg font-black text-red-600">{currency} {total}</div>
                </div>
              </div>

              {/* Passengers */}
              <div className="mt-4">
                <div className="text-[9px] font-black uppercase tracking-widest text-zinc-400 mb-1.5">Passengers</div>
                <div className="flex flex-wrap gap-x-4 gap-y-1">
                  {(paxList.length > 0 ? paxList : passengers).map((p: any, i: number) => (
                    <div key={i} className="flex items-center gap-1.5">
                      <div className="w-5 h-5 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
                        <span className="text-[9px] font-black text-red-600">{i + 1}</span>
                      </div>
                      <span className="text-xs font-bold text-zinc-700 uppercase tracking-wide">
                        {p.paxtitle || ""} {p.firstname} {p.lastname}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Right: Tear-off stub */}
            <div className="relative w-[140px] flex-shrink-0">
              {/* Dashed vertical separator with cutout circles */}
              <div className="absolute left-0 top-0 bottom-0 w-0">
                <div className="absolute -left-3 -top-1 w-6 h-6 bg-zinc-100 rounded-full" />
                <div className="absolute -left-3 -bottom-1 w-6 h-6 bg-zinc-100 rounded-full" />
                <div className="absolute left-0 top-4 bottom-4 border-l-2 border-dashed border-zinc-200" />
              </div>

              <div className="h-full flex flex-col items-center justify-center px-4 py-5 gap-3 bg-zinc-50">
                <div className="text-center">
                  <div className="text-[9px] font-black uppercase tracking-widest text-zinc-400">PNR</div>
                  <div className="text-xl font-black text-zinc-900 tracking-widest">{pnr}</div>
                </div>
                {ticketDeadline && (
                  <div className="text-center">
                    <div className="text-[9px] font-black uppercase tracking-widest text-zinc-400">Ticket By</div>
                    <div className="text-[11px] font-bold text-zinc-600 mt-0.5">{ticketDeadline}</div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Bottom — View Booking link */}
          {link && (
            <div className="px-6 pb-4">
              <a
                href={link}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full py-3 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-white font-black text-sm uppercase tracking-wider transition-colors flex items-center justify-center gap-2 shadow-md"
              >
                View Booking <ChevronRight className="w-4 h-4" />
              </a>
            </div>
          )}
        </motion.div>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-3">
      {/* Header */}
      <div className="bg-red-600 rounded-xl px-4 py-3 flex items-center justify-between">
        <div>
          <div className="text-white font-black text-base uppercase tracking-wide">Passenger Details</div>
          <div className="text-red-200 text-xs mt-0.5 font-bold">{totalPax} passenger{totalPax !== 1 ? "s" : ""} · Booking #{bookingId}</div>
        </div>
        <User className="w-5 h-5 text-white/60" />
      </div>

      {/* Passenger tabs */}
      {totalPax > 1 && (
        <div className="flex gap-1.5 bg-zinc-200 rounded-xl p-1">
          {Array.from({ length: totalPax }, (_, i) => {
            const filled = passengers[i].firstname.trim() && passengers[i].lastname.trim();
            return (
              <button
                key={i}
                onClick={() => setActivePax(i)}
                className={cn(
                  "flex-1 py-2 rounded-lg text-xs font-black uppercase tracking-wider transition-all flex items-center justify-center gap-1.5",
                  activePax === i
                    ? "bg-red-600 text-white shadow-md"
                    : "text-zinc-500 hover:text-zinc-700 hover:bg-zinc-100"
                )}
              >
                {filled && <Check className="w-3 h-3" />}
                Passenger {i + 1}
              </button>
            );
          })}
        </div>
      )}

      {/* Form fields */}
      <div className="bg-white border border-zinc-200 rounded-2xl p-4 space-y-3 shadow-sm">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelCls}>First Name</label>
            <input className={inputCls} placeholder="John" value={pax.firstname}
              onChange={(e) => updateField(activePax, "firstname", e.target.value)} />
          </div>
          <div>
            <label className={labelCls}>Last Name</label>
            <input className={inputCls} placeholder="Doe" value={pax.lastname}
              onChange={(e) => updateField(activePax, "lastname", e.target.value)} />
          </div>
        </div>
        <div>
          <label className={labelCls}>Date of Birth</label>
          <input type="date" className={inputCls} value={pax.birthdate}
            onChange={(e) => updateField(activePax, "birthdate", e.target.value)} />
        </div>
        <div>
          <label className={labelCls}>Phone Number</label>
          <input type="tel" className={inputCls} placeholder="+1 234 567 8900" value={pax.phone}
            onChange={(e) => updateField(activePax, "phone", e.target.value)} />
        </div>
        <div>
          <label className={labelCls}>Email</label>
          <input type="email" className={inputCls} placeholder="john@example.com" value={pax.email}
            onChange={(e) => updateField(activePax, "email", e.target.value)} />
        </div>
      </div>

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={!isComplete || submitting}
        className={cn(
          "w-full py-3 rounded-xl font-black text-sm uppercase tracking-wider transition-all flex items-center justify-center gap-2 shadow-md",
          isComplete && !submitting
            ? "bg-red-600 hover:bg-red-700 text-white"
            : "bg-zinc-200 text-zinc-400 cursor-not-allowed"
        )}
      >
        {submitting ? (
          <><Loader2 className="w-4 h-4 animate-spin" /> Confirming...</>
        ) : (
          <><Check className="w-4 h-4" /> Confirm Booking</>
        )}
      </button>
    </div>
  );
}

// ─── Flight Results ───────────────────────────────────────────────────────────

function FlightResults({ data, outboundSelected, onFlightClick }: {
  data: FlightResponse;
  outboundSelected: boolean;
  onFlightClick: (flight: Flight, ctx: BookingContext) => void;
}) {
  const outbound = data.data.filter((f) => f.direction === "Outbound");
  const inbound = data.data.filter((f) => f.direction === "Return");
  const isRT = data.context.triptype === "RT";
  // Disable return cards if RT and outbound not yet selected
  const returnDisabled = isRT && !outboundSelected;

  return (
    <div className="p-4 space-y-4">
      <div className="bg-red-600 rounded-xl px-4 py-3 flex items-center justify-between">
        <div>
          <div className="text-white font-black text-base uppercase tracking-wide">{data.header}</div>
          <div className="text-red-200 text-sm mt-0.5 font-bold">{data.sub_header}</div>
        </div>
        <Plane className="w-5 h-5 text-white/60 rotate-90" />
      </div>

      {outbound.length > 0 && (
        <div className="space-y-2.5">
          <p className="text-xs font-black uppercase tracking-[0.2em] text-blue-600 px-1">Outbound Flights</p>
          {outbound.map((f, i) => (
            <FlightCard key={i} flight={f} context={data.context} onClick={() => onFlightClick(f, data.context)} />
          ))}
        </div>
      )}

      {inbound.length > 0 && (
        <div className="space-y-2.5">
          <p className="text-xs font-black uppercase tracking-[0.2em] text-emerald-600 px-1">
            Return Flights
            {returnDisabled && <span className="text-zinc-400 ml-2 normal-case tracking-normal font-bold">— select an outbound flight first</span>}
          </p>
          {inbound.map((f, i) => (
            <FlightCard key={i} flight={f} context={data.context} disabled={returnDisabled} onClick={() => onFlightClick(f, data.context)} />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

const THREAD_ID = "user-session-1";

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Hello! I'm your personal flight assistant. Where are you flying to today?",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedFlight, setSelectedFlight] = useState<Flight | null>(null);
  const [flightContext, setFlightContext] = useState<BookingContext | null>(null);
  const [selectedFareId, setSelectedFareId] = useState<number | null>(null);
  const [submittingFare, setSubmittingFare] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  // RT two-step: store outbound selection until return flight is picked
  const [outboundSelection, setOutboundSelection] = useState<{ flight: Flight; cls: FlightClass } | null>(null);
  // Passenger form state
  const [activeBookingId, setActiveBookingId] = useState<number | null>(null);
  const [showPassengerForm, setShowPassengerForm] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const addToast = useCallback((type: ToastType, title: string, message?: string) => {
    const id = Date.now().toString();
    setToasts((prev) => [...prev, { id, type, title, message }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4500);
  }, []);

  const sendToBot = useCallback(async (text: string) => {
    const res = await axios.post("http://127.0.0.1:8000/chat", {
      message: text, thread_id: THREAD_ID,
    });
    return {
      response: res.data.response as string,
      flightResults: (res.data.flight_results as FlightResponse | null) ?? null,
      ancillaryResults: (res.data.ancillary_results as AncillaryResponse | null) ?? null,
    };
  }, []);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return;
    setMessages((prev) => [...prev, {
      id: Date.now().toString(), role: "user", content: text, timestamp: new Date(),
    }]);
    setIsLoading(true);
    try {
      const { response, flightResults, ancillaryResults } = await sendToBot(text);
      setMessages((prev) => [...prev, {
        id: (Date.now() + 1).toString(), role: "assistant",
        content: response, timestamp: new Date(), flightResults, ancillaryResults,
      }]);
    } catch {
      setMessages((prev) => [...prev, {
        id: (Date.now() + 1).toString(), role: "assistant",
        content: "Sorry, I couldn't reach the server. Please try again.",
        timestamp: new Date(),
      }]);
    } finally {
      setIsLoading(false);
    }
  }, [isLoading, sendToBot]);

  const handleSend = () => { sendMessage(input); setInput(""); };

  const handleClassSelect = async (cls: FlightClass) => {
    if (!selectedFlight || !flightContext || submittingFare) return;

    const isRT = flightContext.triptype === "RT";

    // RT step 1: user picked outbound → save it and ask for return
    if (isRT && !outboundSelection && selectedFlight.direction === "Outbound") {
      setOutboundSelection({ flight: selectedFlight, cls });
      setSelectedFlight(null);
      setSelectedFareId(null);
      addToast("success", "Outbound Selected!", "Now pick your return flight.");
      return;
    }

    setSubmittingFare(true);
    setSelectedFareId(cls.fareid);

    // Build booking payload — include return flight info for RT
    const bookingPayload: Record<string, unknown> = {
      flight_id: isRT && outboundSelection ? outboundSelection.cls.flightid : cls.flightid,
      fare_id: isRT && outboundSelection ? outboundSelection.cls.fareid : cls.fareid,
      from_code: flightContext.from_code,
      to_code: flightContext.to_code,
      trip_type: flightContext.triptype || "OW",
      adults: flightContext.adults,
      child: flightContext.child,
      infant: flightContext.infant,
      thread_id: THREAD_ID,
    };

    if (isRT && outboundSelection) {
      bookingPayload.return_flight_id = cls.flightid;
      bookingPayload.return_fare_id = cls.fareid;
    }

    try {
      const res = await axios.post("http://127.0.0.1:8000/book-flight", bookingPayload);
      const meta = res.data?._meta || {};
      const bookingId = meta.booking_id;
      const pnr = meta.pnr || "N/A";
      setSelectedFlight(null);
      setSubmittingFare(false);
      setOutboundSelection(null);
      if (bookingId) setActiveBookingId(bookingId);
      setShowPassengerForm(false); // Reset for new booking
      addToast("success", "Flight Booked!", `PNR: ${pnr}`);
      setIsLoading(true);
      try {
        const primaryFlightId = isRT && outboundSelection ? outboundSelection.cls.flightid : cls.flightid;
        const trigger = `__booking__: Flight booked. PNR: ${pnr}. BookingID: ${bookingId}. FlightID: ${primaryFlightId}. Immediately call check_ancillaries with BookingID ${bookingId} and FlightID ${primaryFlightId}, then collect passenger details.`;
        const { response, flightResults, ancillaryResults } = await sendToBot(trigger);
        setMessages((prev) => [...prev, {
          id: (Date.now() + 1).toString(), role: "assistant",
          content: response, timestamp: new Date(), flightResults, ancillaryResults,
        }]);
      } catch {
        addToast("error", "Couldn't load next step", "Please type something to continue.");
      } finally {
        setIsLoading(false);
      }
    } catch (err: any) {
      setSubmittingFare(false);
      setSelectedFareId(null);
      setOutboundSelection(null);
      addToast("error", "Booking Failed", err?.response?.data?.detail || err?.message || "Something went wrong");
    }
  };

  const [addedAncillaries, setAddedAncillaries] = useState<string[]>([]);

  const renderMessageContent = (msg: Message) => {
    if (msg.role === "assistant" && msg.flightResults) {
      return (
        <>
          {msg.content && (
            <div className="px-4 pt-3 pb-1 text-base leading-relaxed text-zinc-700 font-medium">{msg.content}</div>
          )}
          <FlightResults
            data={msg.flightResults}
            outboundSelected={!!outboundSelection}
            onFlightClick={(f, ctx) => { setSelectedFlight(f); setFlightContext(ctx); setSelectedFareId(null); }}
          />
        </>
      );
    }
    // Only render ancillary cards if available=true and there are items
    if (msg.role === "assistant" && msg.ancillaryResults?.available && msg.ancillaryResults.items?.length > 0) {
      const paxCount = (flightContext?.adults ?? 1) + (flightContext?.child ?? 0);
      return (
        <>
          {msg.content && (
            <div className="px-4 pt-3 pb-1 text-base leading-relaxed text-zinc-700 font-medium">{msg.content}</div>
          )}
          {!showPassengerForm && (
            <AncillaryResults
              data={msg.ancillaryResults}
              paxCount={paxCount}
              onItemAdded={(item) => {
                setAddedAncillaries((prev) => [...prev, String(item.itemid)]);
                addToast("success", "Extra Added!", item.name);
              }}
              onError={(errMsg) => addToast("error", "Add Failed", errMsg)}
              onContinue={() => {
                setShowPassengerForm(true);
              }}
            />
          )}
          {showPassengerForm && (msg.ancillaryResults.booking_id || activeBookingId) && (
            <PassengerForm
              paxCount={paxCount}
              bookingId={msg.ancillaryResults.booking_id || activeBookingId!}
              fromCode={flightContext?.from_code || ""}
              toCode={flightContext?.to_code || ""}
              onSuccess={(pnr) => {
                addToast("success", "Booking Confirmed!", `PNR: ${pnr}`);
              }}
              onError={(errMsg) => {
                addToast("error", "Confirmation Failed", errMsg);
              }}
            />
          )}
        </>
      );
    }
    return <div className="px-4 py-3 whitespace-pre-wrap text-base leading-relaxed">{msg.content}</div>;
  };

  return (
    <div className="flex flex-col h-screen bg-zinc-100 overflow-hidden font-sans">

      {/* ── MESSAGES ── */}
      <main className="flex-1 overflow-y-auto px-4 py-4 bg-zinc-100">
        <div className="max-w-2xl mx-auto space-y-3">
          {/* RT banner: outbound selected, waiting for return */}
          {outboundSelection && (
            <motion.div
              initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-3 bg-red-600 text-white rounded-xl px-4 py-3 shadow-md"
            >
              <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
              <div className="flex-1">
                <div className="font-black text-sm uppercase tracking-wide">Outbound Selected</div>
                <div className="text-red-200 text-xs font-bold mt-0.5">
                  Flight {outboundSelection.flight.flight_number || outboundSelection.flight.flight_code} · {outboundSelection.cls.className} — Now pick a return flight
                </div>
              </div>
              <button
                onClick={() => setOutboundSelection(null)}
                className="p-1 rounded-lg bg-red-700/50 hover:bg-red-700 transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </motion.div>
          )}
          <AnimatePresence initial={false}>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
                className={cn("flex items-end gap-2", msg.role === "user" ? "flex-row-reverse" : "flex-row")}
              >
                {/* Avatar */}
                <div className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mb-1 shadow-sm",
                  msg.role === "assistant" ? "bg-red-600" : "bg-zinc-900"
                )}>
                  {msg.role === "assistant"
                    ? <Plane className="w-4 h-4 text-white rotate-90" />
                    : <User className="w-4 h-4 text-white" />}
                </div>

                {/* Bubble */}
                <div className={cn(
                  "relative max-w-5xl rounded-2xl overflow-hidden shadow-sm",
                  msg.role === "assistant"
                    ? "bg-white border border-zinc-200 text-zinc-800 rounded-bl-sm"
                    : "bg-zinc-900 text-white rounded-br-sm"
                )}>
                  {renderMessageContent(msg)}
                  <p className={cn(
                    "text-xs opacity-40 font-semibold pb-2 px-4 uppercase tracking-wider",
                    msg.role === "user" ? "text-right text-zinc-300" : "text-zinc-400"
                  )}>
                    {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </p>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {/* Typing indicator */}
          {isLoading && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex items-end gap-2">
              <div className="w-8 h-8 rounded-full bg-red-600 flex items-center justify-center shadow-sm">
                <Plane className="w-4 h-4 text-white rotate-90" />
              </div>
              <div className="px-4 py-3 bg-white border border-zinc-200 rounded-2xl rounded-bl-sm shadow-sm">
                <div className="flex gap-1.5 items-center h-4">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-600 animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-red-600 animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-red-600 animate-bounce [animation-delay:300ms]" />
                </div>
              </div>
            </motion.div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* ── INPUT BAR ── */}
      <div className="flex-shrink-0 bg-white border-t-2 border-zinc-200 px-4 py-3">
        <div className="max-w-2xl mx-auto flex items-center gap-2">
          <div className="hidden sm:flex items-center gap-1.5 text-xs text-zinc-400 font-bold uppercase tracking-wider whitespace-nowrap">
            <MapPin className="w-3 h-3 text-red-600" />
            <span>Ask me</span>
          </div>
          <div className="w-px h-4 bg-zinc-200 hidden sm:block" />

          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
            placeholder="Where would you like to fly?"
            className="flex-1 bg-zinc-100 border-2 border-zinc-200 focus:border-red-600 outline-none rounded-xl px-4 py-2.5 text-base text-zinc-900 font-medium placeholder:text-zinc-400 transition-colors"
            disabled={isLoading}
          />

          <motion.button
            whileTap={input.trim() && !isLoading ? { scale: 0.93 } : {}}
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className={cn(
              "flex items-center gap-2 px-4 py-2.5 rounded-xl font-bold uppercase tracking-wider text-base transition-all flex-shrink-0",
              input.trim() && !isLoading
                ? "bg-red-600 hover:bg-red-700 text-white shadow-md shadow-red-200"
                : "bg-zinc-200 text-zinc-400 cursor-not-allowed"
            )}
          >
            {isLoading
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <><Send className="w-4 h-4" /><span className="hidden sm:inline">Send</span></>}
          </motion.button>
        </div>
      </div>

      {/* ── Class Modal ── */}
      <AnimatePresence>
        {selectedFlight && flightContext && (
          <ClassModal
            flight={selectedFlight} context={flightContext}
            submitting={submittingFare} selectedFareId={selectedFareId}
            onClose={() => !submittingFare && setSelectedFlight(null)}
            onSelect={handleClassSelect}
          />
        )}
      </AnimatePresence>

      <ToastContainer toasts={toasts} onDismiss={(id) => setToasts((p) => p.filter((t) => t.id !== id))} />
    </div>
  );
}