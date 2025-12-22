/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, onMounted, useState, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

export class CommissionDashboard extends Component {
    static template = "commission.dashboard";
    static props = ["*"];

    setup() {
        // Use refs for DOM access
        this.root = useRef("root");

        // Try to access services safely
        try {
            this.rpc = useService("rpc");
            this.orm = useService("orm");
            this.actionService = useService("action");
            this.notification = useService("notification");
        } catch (e) {
            console.log("Services not available, will use fallback:", e.message);
            // Services might not be available yet, we'll use fallback
            this.rpc = null;
        }

        this.state = useState({
            data: null,
            loading: true,
            chartLoaded: false,
            error: null,
            currency: null,
            accessDenied: false,
            accessDeniedMessage: '',
        });

        onWillStart(async () => {
            try {
                // Load Chart.js library
                await this.loadChartJS();
                console.log("Chart.js loaded successfully");
            } catch (error) {
                console.error("Error loading Chart.js:", error);
                this.state.error = error.message;
            }
        });

        onMounted(async () => {
            console.log("Component mounted, loading dashboard data...");

            // Refresh button click handler
            const refreshBtn = this.root.el?.querySelector('.dashboard_refresh');
            if (refreshBtn) {
                refreshBtn.addEventListener('click', () => this.onRefreshClick());
            }

            // Load data after DOM is ready
            try {
                if (this.rpc) {
                    await this.loadDashboardData();
                } else {
                    // If RPC not available, try alternative approach
                    await this.loadDashboardDataFallback();
                }
            } catch (error) {
                console.error("Error loading dashboard data:", error);
                this.state.error = error.message;
                this.state.loading = false;
            }
        });
    }

    async loadDashboardDataFallback() {
        // Fallback: use fetch API directly
        console.log("Using fallback method to load data...");
        try {
            const response = await fetch('/commission/dashboard/data', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    method: "call",
                    params: {}
                })
            });

            console.log("Fetch response status:", response.status);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            console.log("Raw response:", result);

            const data = result.result;

            if (!data) {
                throw new Error("No data received from server");
            }

            console.log("Dashboard data received:", data);
            this.state.data = data;

            // Check for access denied
            if (data && data.access_denied) {
                this.state.accessDenied = true;
                this.state.accessDeniedMessage = data.message || 'Accès refusé au tableau de bord';
                console.log("Access denied to dashboard:", this.state.accessDeniedMessage);
                return;
            }

            // Store currency info
            if (data && data.currency) {
                this.state.currency = data.currency;
            }

            // Add null checks before accessing nested properties
            if (data && data.kpis) {
                console.log("Updating KPIs...", data.kpis);
                this.updateKPIs(data.kpis);
            }
            if (data && data.charts) {
                console.log("Updating charts...", data.charts);
                this.updateCharts(data.charts);
            }
            if (data && data.user_info) {
                this.updateCardStyles(data.user_info);
            }

            // Show notification if commission generation occurred
            if (data.generation_result && data.generation_result.count > 0) {
                this.showGenerationNotification(data.generation_result);
            }

            console.log("Dashboard updated successfully!");
        } catch (error) {
            console.error('Error loading dashboard data (fallback):', error);
            this.state.error = error.message;
        } finally {
            this.state.loading = false;
        }
    }

    async loadChartJS() {
        try {
            // Load Chart.js from CDN
            if (typeof Chart === 'undefined') {
                await loadJS("https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js");
            }
            this.state.chartLoaded = true;
        } catch (error) {
            console.error('Error loading Chart.js:', error);
            this.state.chartLoaded = false;
        }
    }

    async loadDashboardData() {
        this.state.loading = true;
        try {
            const data = await this.rpc('/commission/dashboard/data', {});
            this.state.data = data;

            // Check for access denied
            if (data && data.access_denied) {
                this.state.accessDenied = true;
                this.state.accessDeniedMessage = data.message || 'Accès refusé au tableau de bord';
                console.log("Access denied to dashboard:", this.state.accessDeniedMessage);
                return;
            }

            // Store currency info
            if (data && data.currency) {
                this.state.currency = data.currency;
            }

            // Add null checks before accessing nested properties
            if (data && data.kpis) {
                this.updateKPIs(data.kpis);
            }
            if (data && data.charts) {
                this.updateCharts(data.charts);
            }
            if (data && data.user_info) {
                this.updateCardStyles(data.user_info);
            }

            // Show notification if commission generation occurred
            if (data.generation_result && data.generation_result.count > 0) {
                this.showGenerationNotification(data.generation_result);
            }
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.state.error = error.message;
        } finally {
            this.state.loading = false;
        }
    }

    updateKPIs(kpis) {
        // Update KPI values
        this.updateElement('#my_total', this.formatCurrency(kpis.my_total));
        this.updateElement('#my_pending', this.formatCurrency(kpis.my_pending));
        this.updateElement('#my_paid', this.formatCurrency(kpis.my_paid));
        this.updateElement('#my_count', kpis.my_count);

        this.updateElement('#month_total', this.formatCurrency(kpis.my_month_total));
        this.updateElement('#month_count', kpis.my_month_count);

        // Update month label with month name
        const monthLabel = document.querySelector('#month_label');
        if (monthLabel && kpis.current_month_name) {
            monthLabel.textContent = 'Ce mois (' + kpis.current_month_name + ')';
        }

        this.updateElement('#team_total', this.formatCurrency(kpis.team_total));
        this.updateElement('#team_pending', this.formatCurrency(kpis.team_pending));
        this.updateElement('#team_members', kpis.team_members);
    }

    updateCharts(charts) {
        if (!this.state.chartLoaded || typeof Chart === 'undefined') {
            console.warn('Chart.js not loaded yet');
            return;
        }

        // Monthly Trend Chart
        this.createTrendChart(charts.monthly_trend);

        // Status Distribution Chart (as histogram)
        this.createStatusChart(charts.state_distribution);
    }

    createTrendChart(data) {
        const ctx = document.getElementById('trend_chart');
        if (!ctx || typeof Chart === 'undefined') return;

        if (window.trendChart) {
            window.trendChart.destroy();
        }

        window.trendChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(d => d.month),
                datasets: [{
                    label: 'Commission Amount',
                    data: data.map(d => d.amount),
                    borderColor: '#017e84',
                    backgroundColor: 'rgba(1, 126, 132, 0.1)',
                    tension: 0.4,
                    fill: true,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                return 'Amount: ' + this.formatCurrency(context.parsed.y);
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => this.formatCurrency(value)
                        }
                    }
                }
            }
        });
    }

    createStatusChart(data) {
        const ctx = document.getElementById('status_chart');
        if (!ctx || typeof Chart === 'undefined') return;

        if (window.statusChart) {
            window.statusChart.destroy();
        }

        const colors = {
            pending: '#ffc107',
            approved: '#17a2b8',
            paid: '#28a745',
            cancelled: '#dc3545'
        };

        window.statusChart = new Chart(ctx, {
            type: 'bar',  // Changed to bar for histogram
            data: {
                labels: Object.keys(data).map(k => k.charAt(0).toUpperCase() + k.slice(1)),
                datasets: [{
                    label: 'Commission Amount',
                    data: Object.values(data),
                    backgroundColor: Object.keys(data).map(k => colors[k]),
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                return 'Amount: ' + this.formatCurrency(context.parsed.y);
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => this.formatCurrency(value)
                        }
                    }
                }
            }
        });
    }

    updateCardStyles(user_info) {
        // Gray out team commissions card if user doesn't manage a team
        const teamCard = document.querySelector('.col-md-3:has(#team_total)');
        if (teamCard && !user_info.has_team) {
            teamCard.style.opacity = '0.5';
            teamCard.style.filter = 'grayscale(50%)';
            const cardElement = teamCard.querySelector('.dashboard_card');
            if (cardElement) {
                cardElement.style.backgroundColor = '#e9ecef';
            }
        }
    }

    showGenerationResultNotification(result) {
        // Show notification similar to sale order style - ALWAYS show a message
        if (!this.notification) {
            // Fallback to alert if notification service not available
            alert(result.message || 'Actualisation terminée');
            return;
        }

        // Always show notification, even if no commissions created
        if (result.success && result.count > 0) {
            // Success notification with commission details
            this.notification.add(result.message, {
                title: '✓ Commissions générées',
                type: 'success',
                sticky: false,
            });
        } else {
            // Info notification when no new commissions
            const message = result.message || 'Aucune nouvelle commission à générer - vos données sont à jour';
            this.notification.add(message, {
                title: 'ℹ Génération de commissions',
                type: 'info',
                sticky: false,
            });
        }
    }

    showGenerationNotification(result) {
        // Legacy method - kept for backward compatibility
        // Show notification for commission generation with claimable amount
        const message = `${result.count} commission(s) créée(s) - Montant total: ${this.formatCurrency(result.total_amount)}\nMontant réclamable: ${this.formatCurrency(result.claimable_amount || result.total_amount)}`;

        if (this.notification) {
            this.notification.add(message, {
                title: 'Commissions générées',
                type: 'success',
                sticky: false,
            });
        } else {
            // Fallback if notification service not available
            alert(message);
        }
    }

    updateElement(selector, value) {
        const element = document.querySelector(selector);
        if (element) {
            element.textContent = value;
        }
    }

    formatCurrency(value) {
        // Use company currency if available
        if (this.state.currency && this.state.currency.symbol) {
            const formatted = parseFloat(value || 0).toFixed(this.state.currency.decimal_places || 2);
            // Position: 'before' or 'after'
            if (this.state.currency.position === 'after') {
                return formatted + ' ' + this.state.currency.symbol;
            } else {
                return this.state.currency.symbol + ' ' + formatted;
            }
        }

        // Fallback to default formatting
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD'
        }).format(value || 0);
    }

    getStatusBadge(state) {
        const badges = {
            pending: 'warning',
            approved: 'info',
            paid: 'success',
            cancelled: 'danger'
        };
        return badges[state] || 'secondary';
    }

    async onRefreshClick() {
        // Call refresh endpoint which also generates commissions
        const refreshBtn = this.root.el?.querySelector('.dashboard_refresh');

        // Add loading state to button with Odoo-style spinner
        if (refreshBtn) {
            refreshBtn.disabled = true;
            // Use a more visible spinner icon
            refreshBtn.innerHTML = '<i class="fa fa-circle-o-notch fa-spin"></i> Chargement...';
        }

        this.state.loading = true;
        try {
            let data;
            if (this.rpc) {
                data = await this.rpc('/commission/dashboard/refresh', {});
            } else {
                // Fallback
                const response = await fetch('/commission/dashboard/refresh', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        jsonrpc: "2.0",
                        method: "call",
                        params: {}
                    })
                });
                const result = await response.json();
                data = result.result;
            }

            this.state.data = data;

            // Store currency info
            if (data && data.currency) {
                this.state.currency = data.currency;
            }

            // Update UI
            if (data && data.kpis) {
                this.updateKPIs(data.kpis);
            }
            if (data && data.charts) {
                this.updateCharts(data.charts);
            }
            if (data && data.user_info) {
                this.updateCardStyles(data.user_info);
            }

            // Always show notification for commission generation result
            if (data.generation_result) {
                this.showGenerationResultNotification(data.generation_result);
            } else {
                // Fallback if no result returned
                if (this.notification) {
                    this.notification.add('Tableau de bord actualisé', {
                        title: 'Actualisation terminée',
                        type: 'info',
                        sticky: false,
                    });
                }
            }
        } catch (error) {
            console.error('Error refreshing dashboard:', error);
            if (this.notification) {
                this.notification.add('Erreur lors de l\'actualisation: ' + error.message, {
                    title: 'Erreur',
                    type: 'danger',
                    sticky: true,
                });
            } else {
                alert('Erreur: ' + error.message);
            }
        } finally {
            this.state.loading = false;
            // Restore button state
            if (refreshBtn) {
                refreshBtn.disabled = false;
                refreshBtn.innerHTML = '<i class="fa fa-refresh"></i> Actualiser';
            }
        }
    }

    async openCommission(id) {
        if (this.actionService) {
            await this.actionService.doAction({
                type: 'ir.actions.act_window',
                res_model: 'sale.commission',
                res_id: id,
                views: [[false, 'form']],
                target: 'current',
            });
        }
    }

    async openUser(id) {
        if (this.actionService) {
            await this.actionService.doAction({
                type: 'ir.actions.act_window',
                res_model: 'res.users',
                res_id: id,
                views: [[false, 'form']],
                target: 'current',
            });
        }
    }
}

registry.category("actions").add("commission_dashboard", CommissionDashboard);
