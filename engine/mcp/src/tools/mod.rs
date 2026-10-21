mod blocks;
mod homework;
mod read;
mod write;

pub(crate) fn router(
    read_only: bool,
) -> rmcp::handler::server::router::tool::ToolRouter<crate::App> {
    if read_only {
        return crate::App::read_tools();
    }
    crate::App::read_tools() + crate::App::homework_tools() + crate::App::block_tools()
}

#[rmcp::tool_handler(router = crate::tools::router(self.read_only))]
impl rmcp::ServerHandler for crate::App {
    async fn call_tool(
        &self,
        request: rmcp::model::CallToolRequestParams,
        context: rmcp::service::RequestContext<rmcp::RoleServer>,
    ) -> Result<rmcp::model::CallToolResponse, rmcp::ErrorData> {
        let router = router(self.read_only);
        let call = rmcp::handler::server::tool::ToolCallContext::new(self, request, context);
        router.call(call).await
    }
}
