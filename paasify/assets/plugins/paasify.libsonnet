
// Default functions
// =============================
local _metadata_default =
  {
    "ERROR": "Metadata is not set !"
  };

local _fn_empty(vars) =
  {};

local _fn_docker_override (vars, docker_file) = docker_file;


// Library functions
// =============================


// Create a network definition
local DockerNetDef(net_id, net_name=null, net_external=false, net_labels={}, net_ipam={}) =
  std.prune(
  if std.isString(net_id) then
  {
    [net_id]+: {
      name: net_name,
      external: net_external,
      labels: net_labels,
      ipam: net_ipam,
    },
  }
  else {});

// Attach a network to a service
local DockerServiceNet(net_id, net_aliases=[], net_ipv4=null, net_ipv6=null) =
  if std.isString(net_id) then
  {
    networks+: {
      [net_id]: std.prune({
        aliases: net_aliases,
        ipv4_address: net_ipv4,
        ipv6_address: net_ipv6,
      }),
    },
  }
  else {};

// Create ldap base DN from domain
local LdapBaseDNFromDomain( domain, sep='dc')=
  local domain_parts = [ sep + '=' + x for x in std.split(domain, '.')];
  std.join(',', domain_parts);


// Main wrapper
// =============================
{
  local lib_paasify = self,

  // Internal lib
  // =====================

  // Return the current value of input vars
  getConf(name)::
    std.parseJson(std.extVar(name)),


  get_global_vars(vars, fn_global_default, fn_global_assemble)::
    local defaults = fn_global_default(vars);
    local assemble = fn_global_assemble(defaults + vars);
    defaults + assemble,


  // Std lib
  // =====================
  DockerServiceNet:: DockerServiceNet,
  DockerNetDef:: DockerNetDef,
  LdapBaseDNFromDomain:: LdapBaseDNFromDomain,

  main(plugin)::
    // Get plugin config
    local metadata = std.get(plugin, "metadata", default=_metadata_default);

    // Extract user input
    local parent = $.getConf('parent'); // expect a string
    local action = $.getConf('action'); // expect a string
    local args = $.getConf('args'); // expect a dict

    // Extract plugins function
    if plugin.metadata.ident != parent then    # For imports ?
      plugin
    else if action == 'docker_transform' then
      local fn = std.get(plugin, "docker_transform", default=_fn_docker_override);
      fn(args, $.getConf('docker_data'))
    else
      local fn = std.get(plugin, action, default=_fn_empty);
      fn(args),
    #else
    #  out + {
    #    msg: "Action not set !"
    #  },

}

# Run main script !
#main()
