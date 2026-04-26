/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, useState, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class CallCenterDashboard extends Component {
    static template = "call_center.dashboard";
    static props = ["*"];

    setup() {
        this.root = useRef("root");

        try {
            this.rpc = useService("rpc");
            this.notification = useService("notification");
        } catch (e) {
            this.rpc = null;
        }
        try {
            this.action = useService("action");
        } catch (e) {
            this.action = null;
        }

        this.state = useState({
            data: null,
            orders: null,
            loading: true,
            loadingOrders: false,
            error: null,
            activeTab: 'overview',  // 'overview' | 'details'
            currentMonth: null,
            currentYear: null,
            currentQuarter: null,
            periodType: 'month',
            dateFrom: null,
            dateTo: null,
            filterCallCenterId: null,
            availableCallCenters: [],
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
            body: JSON.stringify({ jsonrpc: "2.0", method: "call", params }),
        });
        const result = await response.json();
        return result.result;
    }

    async loadFilterOptions() {
        const options = await this._rpcCall('/call_center/dashboard/filters', {});
        if (options) {
            this.state.availableCallCenters = options.call_centers || [];
        }
    }

    _buildParams(month = null, year = null) {
        const params = { period_type: this.state.periodType };
        if (month) params.month = month;
        if (year) params.year = year;
        if (this.state.periodType === 'quarter' && this.state.currentQuarter) {
            params.quarter = this.state.currentQuarter;
        }
        if (this.state.periodType === 'custom') {
            if (!this.state.dateFrom || !this.state.dateTo) {
                return null;
            }
            params.date_from = this.state.dateFrom;
            params.date_to = this.state.dateTo;
        }
        if (this.state.filterCallCenterId) {
            params.call_center_id = this.state.filterCallCenterId;
        }
        return params;
    }

    async loadDashboardData(month = null, year = null) {
        this.state.loading = true;
        this.state.error = null;
        try {
            const params = this._buildParams(month, year);
            if (!params) {
                this.state.loading = false;
                return;
            }
            const data = await this._rpcCall('/call_center/dashboard/data', params);
            if (!data) {
                throw new Error("No data received from server");
            }
            this.state.data = data;
            this.state.currentMonth = data.current_month;
            this.state.currentYear = data.current_year;
            this.state.currentQuarter = data.current_quarter || null;
            if (this.state.activeTab === 'details') {
                await this.loadOrders();
            }
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.state.error = error.message;
        } finally {
            this.state.loading = false;
        }
    }

    async loadOrders() {
        this.state.loadingOrders = true;
        try {
            const params = this._buildParams(this.state.currentMonth, this.state.currentYear);
            if (!params) {
                this.state.loadingOrders = false;
                return;
            }
            const res = await this._rpcCall('/call_center/dashboard/orders', params);
            this.state.orders = (res && res.orders) || [];
        } catch (error) {
            console.error('Error loading orders:', error);
            this.state.orders = [];
        } finally {
            this.state.loadingOrders = false;
        }
    }

    async onTabChange(tab) {
        this.state.activeTab = tab;
        if (tab === 'details' && this.state.orders === null) {
            await this.loadOrders();
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
                return;
            }
            params.set('date_from', this.state.dateFrom);
            params.set('date_to', this.state.dateTo);
        }
        if (this.state.filterCallCenterId) {
            params.set('call_center_id', this.state.filterCallCenterId);
        }
        window.open('/call_center/dashboard/export?' + params.toString(), '_blank');
    }

    async onPeriodTypeChange(ev) {
        this.state.periodType = ev.target.value;
        const now = new Date();
        if (this.state.periodType === 'quarter') {
            this.state.currentQuarter = Math.ceil((this.state.currentMonth || now.getMonth() + 1) / 3);
        }
        if (this.state.periodType === 'custom') {
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

    async onCallCenterFilterChange(ev) {
        this.state.filterCallCenterId = ev.target.value ? parseInt(ev.target.value) : null;
        // Force orders reload on next visit to Details
        this.state.orders = null;
        await this.loadDashboardData(this.state.currentMonth, this.state.currentYear);
    }

    openRecord(resModel, resId) {
        if (!resId) return;
        if (this.action && this.action.doAction) {
            this.action.doAction({
                type: 'ir.actions.act_window',
                res_model: resModel,
                res_id: resId,
                views: [[false, 'form']],
                target: 'current',
            });
            return;
        }
        // Fallback if the action service is unavailable
        window.open(`/odoo/action-base.action_ui?model=${resModel}&res_id=${resId}`, '_self');
    }

    onOrderClick(orderId) {
        this.openRecord('sale.order', orderId);
    }

    onEventClick(eventId) {
        this.openRecord('calendar.event', eventId);
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

    getRevenue(ccId) {
        if (!this.state.data) return 0;
        return this.state.data.revenue[String(ccId)] || 0;
    }

    getCancelled(ccId) {
        if (!this.state.data) return 0;
        return this.state.data.cancelled[String(ccId)] || 0;
    }

    getRevenueCount(ccId) {
        if (!this.state.data) return 0;
        return this.state.data.revenue_count[String(ccId)] || 0;
    }

    getCancelledCount(ccId) {
        if (!this.state.data) return 0;
        return this.state.data.cancelled_count[String(ccId)] || 0;
    }
}

registry.category("actions").add("call_center_dashboard", CallCenterDashboard);
