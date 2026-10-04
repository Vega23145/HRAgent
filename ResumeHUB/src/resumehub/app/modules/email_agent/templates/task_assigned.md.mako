## Task assignment
<%
    role_title = role.get("title", role_id)
%>
Subject: Take-Home Task – ${role_title}

Hi ${candidate_name},

Thank you for your interest in **${role_title}**. As the next step, we'd like you to complete a short take-home task.

**Task:** ${task_title}

${task_description}

**Instructions:**
${task_instructions}

% if task_deadline:
**Deadline:** ${task_deadline}
% endif

Please submit your work through our portal when you're ready.

Best regards,
${sender_name}
${org_name}
