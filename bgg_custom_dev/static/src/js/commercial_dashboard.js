/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, useState, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class CommercialDashboard extends Component {
    static template = "commercial.dashboard";
    static props = ["*"];

    setup() {
        this.root = useRef("root");

        try {
            this.rpc = useService("rpc");
            this.notification = useService("notification");
        } catch (e) {
            console.log("Services not available:", e.message);
            this.rpc = null;
        }

        this.state = useState({
            data: null,
            loading: true,
            error: null,
            currentMonth: null,
            currentYear: null,
            currentQuarter: null,
            periodType: 'month',
            dateFrom: null,
            dateTo: null,
            filterUserId: null,
            filterCompanyId: null,
            availableUsers: [],
            availableCompanies: [],
        });

        onMounted(async () => {
            try {
                await this.loadFilterOptions();
            } catch (error) {
                console.error("Error loading filter options:", error);
            }
            try {
                await this.loadDashboardData();
            } catch (error) {
                console.error("Error loading dashboard data:", error);
                this.state.error = error.message;
                this.state.loading = false;
            }
        });
    }

    async _rpcCall(url, params) {
        if (this.rpc) {
            return await this.rpc(url, params);
        }
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: params,
            }),
        });
        const result = await response.json();
        return result.result;
    }

    async loadFilterOptions() {
        const options = await this._rpcCall('/commercial/dashboard/filters', {});
        if (options) {
            this.state.availableUsers = options.users || [];
            this.state.availableCompanies = options.companies || [];
        }
    }

    async loadDashboardData(month = null, year = null) {
        this.state.loading = true;
        this.state.error = null;
        try {
            const params = {
                period_type: this.state.periodType,
            };
            if (month) params.month = month;
            if (year) params.year = year;
            if (this.state.periodType === 'quarter' && this.state.currentQuarter) {
                params.quarter = this.state.currentQuarter;
            }
            if (this.state.periodType === 'custom') {
                if (!this.state.dateFrom || !this.state.dateTo) {
                    // Wait for the user to pick both dates
                    this.state.loading = false;
                    return;
                }
                params.date_from = this.state.dateFrom;
                params.date_to = this.state.dateTo;
            }
            if (this.state.filterUserId) params.user_id = this.state.filterUserId;
            if (this.state.filterCompanyId) params.company_id = this.state.filterCompanyId;

            const data = await this._rpcCall('/commercial/dashboard/data', params);

            if (!data) {
                throw new Error("No data received from server");
            }

            this.state.data = data;
            this.state.currentMonth = data.current_month;
            this.state.currentYear = data.current_year;
            this.state.currentQuarter = data.current_quarter || null;
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.state.error = error.message;
        } finally {
            this.state.loading = false;
        }
    }

    async onPrevPeriod() {
        if (this.state.periodType === 'custom') return;
        let m = this.state.currentMonth;
        let y = this.state.currentYear;
        let q = this.state.currentQuarter;

        if (this.state.periodType === 'month') {
            m -= 1;
            if (m < 1) { m = 12; y--; }
        } else if (this.state.periodType === 'quarter') {
            q -= 1;
            if (q < 1) { q = 4; y--; }
            m = (q - 1) * 3 + 1;
        } else {
            y -= 1;
            m = 1;
        }

        this.state.currentQuarter = q;
        await this.loadDashboardData(m, y);
    }

    async onNextPeriod() {
        if (this.state.periodType === 'custom') return;
        let m = this.state.currentMonth;
        let y = this.state.currentYear;
        let q = this.state.currentQuarter;

        if (this.state.periodType === 'month') {
            m += 1;
            if (m > 12) { m = 1; y++; }
        } else if (this.state.periodType === 'quarter') {
            q += 1;
            if (q > 4) { q = 1; y++; }
            m = (q - 1) * 3 + 1;
        } else {
            y += 1;
            m = 1;
        }

        this.state.currentQuarter = q;
        await this.loadDashboardData(m, y);
    }

    async onRefresh() {
        await this.loadDashboardData(this.state.currentMonth, this.state.currentYear);
    }

    onExportExcel() {
        const params = new URLSearchParams();
        if (this.state.currentMonth) params.set('month', this.state.currentMonth);
        if (this.state.currentYear) params.set('year', this.state.currentYear);
        params.set('period_type', this.state.periodType);
        if (this.state.currentQuarter) params.set('quarter', this.state.currentQuarter);
        if (this.state.periodType === 'custom') {
            if (!this.state.dateFrom || !this.state.dateTo) {
                return;  // Nothing to export until both dates are set
            }
            params.set('date_from', this.state.dateFrom);
            params.set('date_to', this.state.dateTo);
        }
        if (this.state.filterUserId) params.set('user_id', this.state.filterUserId);
        if (this.state.filterCompanyId) params.set('company_id', this.state.filterCompanyId);
        window.open('/commercial/dashboard/export?' + params.toString(), '_blank');
    }

    async onPeriodTypeChange(ev) {
        this.state.periodType = ev.target.value;
        const now = new Date();
        if (this.state.periodType === 'quarter') {
            this.state.currentQuarter = Math.ceil((this.state.currentMonth || now.getMonth() + 1) / 3);
        }
        if (this.state.periodType === 'custom') {
            // Default range to the current month so the user has a starting point
            if (!this.state.dateFrom || !this.state.dateTo) {
                const y = now.getFullYear();
                const m = now.getMonth();
                const pad = (n) => String(n).padStart(2, '0');
                const first = new Date(y, m, 1);
                const last = new Date(y, m + 1, 0);
                this.state.dateFrom = `${first.getFullYear()}-${pad(first.getMonth() + 1)}-${pad(first.getDate())}`;
                this.state.dateTo = `${last.getFullYear()}-${pad(last.getMonth() + 1)}-${pad(last.getDate())}`;
            }
        }
        await this.loadDashboardData(this.state.currentMonth, this.state.currentYear);
    }

    async onDateFromChange(ev) {
        this.state.dateFrom = ev.target.value || null;
        if (this.state.dateFrom && this.state.dateTo) {
            await this.loadDashboardData(this.state.currentMonth, this.state.currentYear);
        }
    }

    async onDateToChange(ev) {
        this.state.dateTo = ev.target.value || null;
        if (this.state.dateFrom && this.state.dateTo) {
            await this.loadDashboardData(this.state.currentMonth, this.state.currentYear);
        }
    }

    async onUserFilterChange(ev) {
        this.state.filterUserId = ev.target.value ? parseInt(ev.target.value) : null;
        await this.loadDashboardData(this.state.currentMonth, this.state.currentYear);
    }

    async onCompanyFilterChange(ev) {
        this.state.filterCompanyId = ev.target.value ? parseInt(ev.target.value) : null;
        await this.loadDashboardData(this.state.currentMonth, this.state.currentYear);
    }

    formatCurrency(value) {
        if (!this.state.data || !this.state.data.currency) {
            return parseFloat(value || 0).toFixed(2);
        }
        const c = this.state.data.currency;
        const formatted = parseFloat(value || 0).toFixed(c.decimal_places || 2);
        if (c.position === 'after') {
            return formatted + ' ' + c.symbol;
        }
        return c.symbol + ' ' + formatted;
    }

    formatPercent(value) {
        return (value || 0) + '%';
    }

    getUserCallData(userId) {
        if (!this.state.data) return {};
        return this.state.data.rdv_call[String(userId)] || {};
    }

    getUserComData(userId) {
        if (!this.state.data) return {};
        return this.state.data.rdv_commercial[String(userId)] || {};
    }

    getUserDerived(userId) {
        if (!this.state.data) return {};
        return this.state.data.derived[String(userId)] || {};
    }
}

registry.category("actions").add("commercial_dashboard", CommercialDashboard);
