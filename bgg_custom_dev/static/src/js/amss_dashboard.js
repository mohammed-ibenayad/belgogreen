/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

// For each card: does an increase mean good news?
const HIGHER_IS_BETTER = {
    ca_net: true,
    ventes_confirmees: true,
    tx_conversion: true,
    dossiers_bloques: false,
};

export class AmssManagementDashboard extends Component {
    static template = "bgg_custom_dev.AmssManagementDashboard";
    static props = ["*"];

    setup() {
        this.action = useService("action");
        this.state = useState({
            data: null,
            loading: true,
            error: null,
            activeTab: "direction",
            currentMonth: null,
            currentYear: null,
            currentQuarter: null,
            periodType: "month",
            dateFrom: null,
            dateTo: null,
            filterCompanyId: null,
            filterPaymentTermId: null,
            availableCompanies: [],
            availablePaymentTerms: [],
        });
        onWillStart(async () => {
            try {
                const options = await rpc("/amss/dashboard/filters", {});
                this.state.availableCompanies = options.companies || [];
                this.state.availablePaymentTerms = options.payment_terms || [];
            } catch (error) {
                this.state.error = error.data?.message || error.message;
            }
            await this.loadData();
        });
    }

    /**
     * Filter parameters sent to the server, or null while a custom range is
     * incomplete.
     */
    filterParams(month = null, year = null) {
        const params = { period_type: this.state.periodType };
        if (month) params.month = month;
        if (year) params.year = year;
        if (this.state.periodType === "quarter" && this.state.currentQuarter) {
            params.quarter = this.state.currentQuarter;
        }
        if (this.state.periodType === "custom") {
            if (!this.state.dateFrom || !this.state.dateTo) {
                return null;
            }
            params.date_from = this.state.dateFrom;
            params.date_to = this.state.dateTo;
        }
        if (this.state.filterCompanyId) params.company_id = this.state.filterCompanyId;
        if (this.state.filterPaymentTermId) params.payment_term_id = this.state.filterPaymentTermId;
        return params;
    }

    async loadData(month = null, year = null) {
        const params = this.filterParams(month, year);
        if (!params) {
            this.state.loading = false;
            return;
        }
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await rpc("/amss/dashboard/data", params);
            this.state.data = data;
            this.state.currentMonth = data.current_month;
            this.state.currentYear = data.current_year;
            this.state.currentQuarter = data.current_quarter || null;
        } catch (error) {
            this.state.error = error.data?.message || error.message;
        } finally {
            this.state.loading = false;
        }
    }

    // ------------------------------------------------------------------
    // Period and filters (same behaviour as Suivi Commercial)
    // ------------------------------------------------------------------

    async shiftPeriod(step) {
        if (this.state.periodType === "custom") return;
        let m = this.state.currentMonth;
        let y = this.state.currentYear;
        let q = this.state.currentQuarter;
        if (this.state.periodType === "month") {
            m += step;
            if (m < 1) { m = 12; y--; }
            if (m > 12) { m = 1; y++; }
        } else if (this.state.periodType === "quarter") {
            q += step;
            if (q < 1) { q = 4; y--; }
            if (q > 4) { q = 1; y++; }
            m = (q - 1) * 3 + 1;
        } else {
            y += step;
            m = 1;
        }
        this.state.currentQuarter = q;
        await this.loadData(m, y);
    }

    onPrevPeriod() {
        return this.shiftPeriod(-1);
    }

    onNextPeriod() {
        return this.shiftPeriod(1);
    }

    onRefresh() {
        return this.loadData(this.state.currentMonth, this.state.currentYear);
    }

    async onPeriodTypeChange(ev) {
        this.state.periodType = ev.target.value;
        const now = new Date();
        if (this.state.periodType === "quarter") {
            this.state.currentQuarter = Math.ceil((this.state.currentMonth || now.getMonth() + 1) / 3);
        }
        if (this.state.periodType === "custom" && (!this.state.dateFrom || !this.state.dateTo)) {
            const pad = (n) => String(n).padStart(2, "0");
            const first = new Date(now.getFullYear(), now.getMonth(), 1);
            const last = new Date(now.getFullYear(), now.getMonth() + 1, 0);
            this.state.dateFrom = `${first.getFullYear()}-${pad(first.getMonth() + 1)}-${pad(first.getDate())}`;
            this.state.dateTo = `${last.getFullYear()}-${pad(last.getMonth() + 1)}-${pad(last.getDate())}`;
        }
        await this.loadData(this.state.currentMonth, this.state.currentYear);
    }

    async onDateFromChange(ev) {
        this.state.dateFrom = ev.target.value || null;
        await this.loadData(this.state.currentMonth, this.state.currentYear);
    }

    async onDateToChange(ev) {
        this.state.dateTo = ev.target.value || null;
        await this.loadData(this.state.currentMonth, this.state.currentYear);
    }

    async onCompanyFilterChange(ev) {
        this.state.filterCompanyId = ev.target.value ? parseInt(ev.target.value) : null;
        await this.loadData(this.state.currentMonth, this.state.currentYear);
    }

    /** Open the records behind a card or a bar, with the same filters. */
    async openCard(card) {
        const params = this.filterParams(this.state.currentMonth, this.state.currentYear);
        if (!params) return;
        try {
            const action = await rpc("/amss/dashboard/open", { ...params, card });
            await this.action.doAction(action);
        } catch (error) {
            this.state.error = error.data?.message || error.message;
        }
    }

    async onPaymentTermFilterChange(ev) {
        this.state.filterPaymentTermId = ev.target.value ? parseInt(ev.target.value) : null;
        await this.loadData(this.state.currentMonth, this.state.currentYear);
    }

    onExportExcel() {
        const params = new URLSearchParams();
        if (this.state.currentMonth) params.set("month", this.state.currentMonth);
        if (this.state.currentYear) params.set("year", this.state.currentYear);
        params.set("period_type", this.state.periodType);
        if (this.state.currentQuarter) params.set("quarter", this.state.currentQuarter);
        if (this.state.periodType === "custom") {
            if (!this.state.dateFrom || !this.state.dateTo) return;
            params.set("date_from", this.state.dateFrom);
            params.set("date_to", this.state.dateTo);
        }
        if (this.state.filterCompanyId) params.set("company_id", this.state.filterCompanyId);
        if (this.state.filterPaymentTermId) params.set("payment_term_id", this.state.filterPaymentTermId);
        window.open("/amss/dashboard/export?" + params.toString(), "_blank");
    }

    // ------------------------------------------------------------------
    // Formatting
    // ------------------------------------------------------------------

    get currencySymbol() {
        return this.state.data?.currency?.symbol || "€";
    }

    formatAmount(value) {
        const c = this.state.data?.currency || {};
        const text = (value || 0).toLocaleString("fr-BE", {
            minimumFractionDigits: c.decimal_places ?? 2,
            maximumFractionDigits: c.decimal_places ?? 2,
        });
        return c.position === "before" ? `${this.currencySymbol} ${text}` : `${text} ${this.currencySymbol}`;
    }

    formatThousands(value) {
        return Math.round((value || 0) / 1000).toLocaleString("fr-BE");
    }

    formatKAmount(value) {
        return `${this.formatThousands(value)} k${this.currencySymbol}`;
    }

    formatDelta(key) {
        const card = this.state.data.cards[key];
        if (card.delta === null || card.delta === undefined) return "";
        const sign = card.delta > 0 ? "+" : card.delta < 0 ? "−" : "±";
        const abs = Math.abs(card.delta);
        const unit = key === "ca_net" ? " %" : key === "tx_conversion" ? " pts" : "";
        return `${sign}${abs}${unit} vs ${this.state.data.previous_label}`;
    }

    deltaClass(key) {
        const card = this.state.data.cards[key];
        if (!card.delta) return "amss_delta_neutral";
        const good = (card.delta > 0) === HIGHER_IS_BETTER[key];
        return good ? "amss_delta_good" : "amss_delta_bad";
    }

    barWidth(key) {
        const cash = this.state.data.cash_flow;
        const max = Math.max(cash.signe, cash.facture, cash.encaisse, 0);
        if (!max) return "0%";
        return `${Math.max(0, (cash[key] / max) * 100)}%`;
    }

    orderBookWidth(key) {
        const book = this.state.data.order_book;
        const max = Math.max(
            book.carnet_a_planifier, book.carnet_planifies, book.carnet_en_cours, book.carnet_bloques, 0);
        if (!max) return "0%";
        return `${(book[key] / max) * 100}%`;
    }
}

registry.category("actions").add("amss_management_dashboard", AmssManagementDashboard);
