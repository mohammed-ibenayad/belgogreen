/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, onMounted, useState, useRef } from "@odoo/owl";
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
        });

        onMounted(async () => {
            try {
                await this.loadDashboardData();
            } catch (error) {
                console.error("Error loading dashboard data:", error);
                this.state.error = error.message;
                this.state.loading = false;
            }
        });
    }

    async loadDashboardData(month = null, year = null) {
        this.state.loading = true;
        this.state.error = null;
        try {
            let data;
            const params = {};
            if (month) params.month = month;
            if (year) params.year = year;

            if (this.rpc) {
                data = await this.rpc('/commercial/dashboard/data', params);
            } else {
                const response = await fetch('/commercial/dashboard/data', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        jsonrpc: "2.0",
                        method: "call",
                        params: params,
                    }),
                });
                const result = await response.json();
                data = result.result;
            }

            if (!data) {
                throw new Error("No data received from server");
            }

            this.state.data = data;
            this.state.currentMonth = data.current_month;
            this.state.currentYear = data.current_year;
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.state.error = error.message;
        } finally {
            this.state.loading = false;
        }
    }

    async onPrevMonth() {
        let m = this.state.currentMonth - 1;
        let y = this.state.currentYear;
        if (m < 1) { m = 12; y--; }
        await this.loadDashboardData(m, y);
    }

    async onNextMonth() {
        let m = this.state.currentMonth + 1;
        let y = this.state.currentYear;
        if (m > 12) { m = 1; y++; }
        await this.loadDashboardData(m, y);
    }

    async onRefresh() {
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
