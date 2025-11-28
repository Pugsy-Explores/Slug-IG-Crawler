# from . import RootResponse

# parsed = RootResponse.model_validate(response_json)

# # Works for timeline:
# if hasattr(parsed.data, "xdt_api__v1__feed__user_timeline_graphql_connection"):
#     for edge in parsed.data.xdt_api__v1__feed__user_timeline_graphql_connection.edges or []:
#         print(edge.node.owner.username, edge.node.caption.text)

# # Works for shortcode:
# if hasattr(parsed.data, "xdt_api__v1__media__shortcode__web_info"):
#     item = parsed.data.xdt_api__v1__media__shortcode__web_info.items[0]
#     print(item.owner.username, item.caption.text)
