local paasify = import 'paasify.libsonnet';


# Internal functions
# -------------------------------------

# Base routing
local LabelsTraefik(svc, domain, entrypoints, port, group) =
  {
    ["traefik.enable"]: "true",
    ["traefik.group"]: group,
    ["traefik.http.routers." + svc + ".rule"]: 'Host(`' + domain + '`)',
    ["traefik.http.routers." + svc + ".entrypoints"]: entrypoints,
    ["traefik.http.routers." + svc + ".service"]: svc,
    ["traefik.http.services." + svc + ".loadbalancer.server.port"]: std.format("%s", port),
  };

# Middleware
local LabelsTraefikAuthelia(svc, authservice) =
  if std.isString(authservice) && std.length(authservice) > 0 then
    {
      ["traefik.http.routers." + svc + ".middlewares"]: authservice + '@docker',
    } else {};

# TLS management
local LabelsTraefikTls(svc, status) =
  if status == true then
  {
    ["traefik.http.routers." + svc + ".tls"]: "true",
  } else {};

local LabelsTraefikCertResolver(svc, name) =
  if std.isString(name) && std.length(name) > 0 then
  LabelsTraefikTls(svc, true) + {
    ["traefik.http.routers." + svc + ".tls.certresolver"]: name,
  } else {};

# Networking
local TraefikSvcNetwork(id, name) =
  if std.isString(id) then
  {
    [id]: null,
  } else {};

local TraefikPrjNetwork(id, name, external) =
  if std.isString(id) then
  {
    [id]+: {
      name: name
    },
  } +
  if external == true then
  {
    [id]+: {
      external: true,
    },
  } else {}
  else {};



# Plugin API
# -------------------------------------



local plugin = {

  // Provides plugin metadata
  metadata: {
      name: "Traefik Service",
      description: 'Bind service to traefik instance',

      author: "mrjk",
      email: '',
      license: '',
      version: '',

      require: '',
      api: 1,
      jsonschema: {},
    },

  // Return global vars
  default_vars(vars)::
    {

      # Default settings
      # --------------------------

      // app_name: vars.stack_name,
      // app_domain: vars.prj_namespace,
      // // app_name: vars.paasify_stack,
      // // app_fqdn: vars.paasify_stack + '.' + vars.app_domain,


      // # Compose structure
      // # --------------------------
      // app_service: vars.stack_service,

      // app_network: vars.stack_network,
      // app_network_external: false,
      // app_network_name: vars.prj_namespace + vars.paasify_sep + vars.stack_name,

      # App exposition
      # --------------------------
      # Required by API:
      traefik_network_name: vars.prj_namespace + vars.paasify_sep + 'traefik', // vars.app_network_name
      traefik_net_ident: vars.app_network, // vars.app_network
      traefik_net_external: true,
      traefik_svc_ident: vars.app_service , // vars.app_service
      traefik_svc_port: vars.app_port , // vars.app_port
      traefik_svc_group: vars.prj_namespace + vars.paasify_sep + 'traefik',

      traefik_svc_name: vars.prj_namespace + vars.paasify_sep + vars.app_service,
      traefik_svc_domain: vars.app_fqdn,
      traefik_svc_entrypoints: "front-http",
      traefik_svc_auth: null,
      traefik_svc_tls: null,
      traefik_svc_certresolver: null,


      // traefik_svc_name: std.prune(default_svc_name)[0],
      // traefik_svc_domain: std.prune(default_svc_domain)[0],

      // traefik_svc_entrypoints: std.prune(default_svc_entrypoints)[0],
      // traefik_svc_auth: std.get(conf, 'traefik_svc_auth', default=null),
      // traefik_svc_tls: std.get(conf, 'traefik_svc_tls', default=false),
      // traefik_svc_certresolver: std.get(conf, 'traefik_svc_certresolver', default=null),

    },

  override_vars(vars):: 
    
    {
      //app_fqdn: vars.app_name + '.' + vars.app_domain,
      // app_name: vars.paasify_stack,
      // app_fqdn: vars.paasify_stack + '.' + vars.app_domain,

    },

    // docker_override
  docker_override (vars, docker_file)::
    docker_file + {

      //["x-trafik-svc"]: vars,

      # Append stack network
      networks+: TraefikPrjNetwork(
        vars.traefik_net_ident,
        vars.traefik_network_name,
        vars.traefik_net_external),

      # Apply per services labels
      services+: {
        [vars.traefik_svc_ident]+: {
          labels+: 
            LabelsTraefik(
              vars.traefik_svc_name,
              vars.traefik_svc_domain,
              vars.traefik_svc_entrypoints,
              vars.traefik_svc_port, 
              vars.traefik_svc_group) 
            + LabelsTraefikAuthelia(
                vars.traefik_svc_name,
                vars.traefik_svc_auth)
            + LabelsTraefikTls(
                vars.traefik_svc_name,
                vars.traefik_svc_tls)
            + LabelsTraefikCertResolver(
                vars.traefik_svc_name,
                vars.traefik_svc_certresolver)
            ,
          networks+: TraefikSvcNetwork(
            vars.traefik_net_ident,
            vars.traefik_network_name),
        },
      },
    },
    

};

paasify.main(plugin)