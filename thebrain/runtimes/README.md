# Platform runtimes

Runtime binaries/environments are not bundled with this source candidate. Add only a runtime that matches the target OS, CPU architecture, ABI, and the configured model backend. Do not copy a macOS/M1 Python environment to Windows/Linux or assume micromamba environments are relocatable. Before a platform is called supported, run the platform-specific dependency, model-load, API, cancellation, and end-to-end evidence tests. The launcher intentionally fails closed when configured paths are absent.
