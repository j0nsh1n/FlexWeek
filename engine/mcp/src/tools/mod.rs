mod blocks;
mod homework;
mod read;
mod write;

pub(crate) fn router() -> rmcp::handler::server::router::tool::ToolRouter<crate::App> {
    crate::App::read_tools() + crate::App::homework_tools() + crate::App::block_tools()
}

#[rmcp::tool_handler(router = crate::tools::router())]
impl rmcp::ServerHandler for crate::App {
    async fn call_tool(
        &self,
        request: rmcp::model::CallToolRequestParams,
        context: rmcp::service::RequestContext<rmcp::RoleServer>,
    ) -> Result<rmcp::model::CallToolResponse, rmcp::ErrorData> {
        let router = router();
        let call = rmcp::handler::server::tool::ToolCallContext::new(self, request, context);
        router.call(call).await
    }
}
