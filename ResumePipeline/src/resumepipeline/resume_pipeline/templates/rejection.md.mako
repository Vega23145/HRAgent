Subject: Application update from ${org_name}

Hello ${candidate_name},

Thank you for taking the time to apply to ${org_name}.

${reason}

Scores for the roles reviewed:
% for role in role_scores:
- ${role["title"]}: ${role["score"]}/100
% endfor

We appreciate your interest. Please consider applying again for future opportunities that match your experience.

Best regards,
${sender_name}
${org_name}