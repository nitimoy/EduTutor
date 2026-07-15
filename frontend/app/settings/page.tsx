import { MainLayout } from "@/components/layout/MainLayout";

export default function SettingsPage() {
    return (
        <MainLayout>
            <div className="p-8 max-w-4xl mx-auto space-y-6">
                <h1 className="text-3xl font-bold text-slate-100">Settings</h1>
                <div className="bg-slate-900/50 p-6 rounded-2xl border border-slate-800 space-y-4 text-slate-300">
                    <p className="text-slate-500 italic">Settings configuration will be implemented in a future update.</p>
                </div>
            </div>
        </MainLayout>
    );
}
