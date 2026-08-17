"""TestLink Mock 数据。

与 testlink.txt 中的接口返回示例保持一致，便于接入适配时对照。

- CASE_DETAILS: get_case_detail 的返回数据（key 为不带横杠的用例 ID）
- TREE_NODES:  get_tree_nodes 的返回数据
"""

# get_case_detail 返回示例：key -> 用例详情
CASE_DETAILS = {
    "C2185677": {
        "item_a": "<p>登录超时应失败</p>",
        "idea_a": (
            "<p>验证FTPS服务登录超时机制是否正常生效。客户端建立FTPS连接后不进行登录认证，"
            "保持连接空闲至超过设备配置的登录超时时间，检查服务器是否主动断开连接；"
            "超时后继续进行登录操作应失败，重新建立FTPS连接后可正常登录，"
            "确保设备能够及时释放空闲会话资源并保证服务正常运行。</p><p><br/></p>"
        ),
        "summary": "topo_lan_wan_usb_storage",
        "condition_a": (
            "<p>样机接入移动硬盘，开启internet FTP服务，开启TLS加密；"
            "wan PC的客户端工具为FileZilla。</p>"
        ),
        "steps": (
            "<table><tbody>"
            "<tr><th>测试步骤</th><th>预期结果</th></tr>"
            "<tr><td>1. 开启FTPS服务，使用FTPS客户端连接服务器，但不输入用户名和密码。</td>"
            "<td>FTPS连接建立成功，服务器等待客户端进行身份认证。</td></tr>"
            "<tr><td>2. 保持连接空闲至超过配置的登录超时时间。</td>"
            "<td>服务器主动断开FTPS连接，超时会话被释放。</td></tr>"
            "<tr><td>3. 在连接超时后继续输入用户名、密码并尝试登录。</td>"
            "<td>登录失败，客户端提示连接已断开或会话已失效。</td></tr>"
            "<tr><td>4. 重新建立FTPS连接并输入正确的用户名和密码登录。</td>"
            "<td>FTPS登录成功，可正常访问文件并执行文件传输操作。</td></tr>"
            "</tbody></table><p><br/></p>"
        ),
        "expected_results": "",
    },
    # 可继续补充更多用例详情
}

# get_tree_nodes 返回示例：test_suite 节点列表（顶层目录/套件）
SUITE_NODES = [
    {"node_id": "4819123", "type": "test_suite", "name": "Function", "case_id": None, "case_count": 21},
    {"node_id": "4819166", "type": "test_suite", "name": "Stability", "case_id": None, "case_count": 12},
    {"node_id": "4819191", "type": "test_suite", "name": "Security", "case_id": None, "case_count": 6},
    {"node_id": "4819204", "type": "test_suite", "name": "Compatibility", "case_id": None, "case_count": 7},
    {"node_id": "4819219", "type": "test_suite", "name": "Cross_module", "case_id": None, "case_count": 14},
    {"node_id": "4819248", "type": "test_suite", "name": "Performance", "case_id": None, "case_count": 12},
]

# get_tree_nodes 返回示例：test_case 节点列表（某个套件下的用例）
TREE_NODES = [
    {"node_id": "4819124", "type": "test_case", "name": "C-2185667:ftps_local_login_with_tls_encryption", "case_id": "C-2185667", "case_count": None},
    {"node_id": "4819126", "type": "test_case", "name": "C-2185668:ftps_local_file_management_and_permission_enforcement", "case_id": "C-2185668", "case_count": None},
    {"node_id": "4819130", "type": "test_case", "name": "C-2185670:ftps_internet_login_with_tls_encryption", "case_id": "C-2185670", "case_count": None},
    {"node_id": "4819128", "type": "test_case", "name": "C-2185669:ftps_local_upload_with_same_file_name", "case_id": "C-2185669", "case_count": None},
    {"node_id": "4819132", "type": "test_case", "name": "C-2185671:ftps_internet_file_management_and_permission_enforcement", "case_id": "C-2185671", "case_count": None},
    {"node_id": "4819134", "type": "test_case", "name": "C-2185672:ftps_internet_file_transfer_with_network_damage", "case_id": "C-2185672", "case_count": None},
    {"node_id": "4819136", "type": "test_case", "name": "C-2185673:ftps_internet_with_wan_ip_change", "case_id": "C-2185673", "case_count": None},
    {"node_id": "4819138", "type": "test_case", "name": "C-2185674:ftps_internet_port_redirection", "case_id": "C-2185674", "case_count": None},
    {"node_id": "4819140", "type": "test_case", "name": "C-2185675:ftps_internet_work_with_port_scan", "case_id": "C-2185675", "case_count": None},
    {"node_id": "4819142", "type": "test_case", "name": "C-2185676:ftps_local_internet_transfer_file_together", "case_id": "C-2185676", "case_count": None},
    {"node_id": "4819144", "type": "test_case", "name": "C-2185677:ftps_login_fali_when_overtime", "case_id": "C-2185677", "case_count": None},
    {"node_id": "4819146", "type": "test_case", "name": "C-2185678:ftps_login_fail_with_incorrect_user_password", "case_id": "C-2185678", "case_count": None},
    {"node_id": "4819148", "type": "test_case", "name": "C-2185679:ftps_internet_port_modify_effective", "case_id": "C-2185679", "case_count": None},
    {"node_id": "4819150", "type": "test_case", "name": "C-2185680:ftps_login_success_anonymous", "case_id": "C-2185680", "case_count": None},
    {"node_id": "4819152", "type": "test_case", "name": "C-2185681:ftps_with_tls_enable_disable", "case_id": "C-2185681", "case_count": None},
    {"node_id": "4819154", "type": "test_case", "name": "C-2185682:ftps_port_release_after_disconnect", "case_id": "C-2185682", "case_count": None},
    {"node_id": "4819156", "type": "test_case", "name": "C-2185683:ftps_local_internet_port_conflict", "case_id": "C-2185683", "case_count": None},
    {"node_id": "4819158", "type": "test_case", "name": "C-2185684:ftps_port_open_when_configured", "case_id": "C-2185684", "case_count": None},
    {"node_id": "4819160", "type": "test_case", "name": "C-2185685:ftps_internet_port_modify_fali_with_incorrect_input", "case_id": "C-2185685", "case_count": None},
    {"node_id": "4819162", "type": "test_case", "name": "C-2185686:ftps_with_ftp_enable_disable", "case_id": "C-2185686", "case_count": None},
    {"node_id": "4819164", "type": "test_case", "name": "C-2185687:ftps_configure_backup_restore", "case_id": "C-2185687", "case_count": None},
]
